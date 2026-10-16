"""Repositorios de dados por usuario (um SQLite local por conta) com
persistencia opcional no Turso via backup/restauracao do arquivo.

Leitura/escrita permanecem locais (rapidas). Quando o Turso esta ativo:
- ao abrir um usuario cujo arquivo local nao existe, restaura do Turso;
- apos escritas, agenda um backup assincrono com debounce (snapshot
  consistente via API de backup do SQLite -> gzip -> blob no Turso).
Isso da persistencia real mesmo no plano free (disco efemero) sem reescrever
as centenas de queries dos repositorios.

Regra de seguranca: se o arquivo local nao existe e a restauracao FALHA (Turso
fora do ar, blob corrompido), o usuario NAO e aberto — criar um banco vazio
levaria o proximo backup a sobrescrever o backup bom na nuvem.
"""
from __future__ import annotations

import atexit
import gzip
import logging
import os
import sqlite3
import tempfile
import threading
from pathlib import Path

from app.bible.repository import BibleRepository
from app.plans.repository import ReadingPlanRepository
from app.study.repository import StudyRepository

logger = logging.getLogger(__name__)

# Resultados de _restore
RESTORED = "restored"   # blob encontrado e gravado localmente
NO_BACKUP = "no_backup"  # Turso respondeu: nao ha backup (usuario novo)
FAILED = "failed"       # erro ao consultar/ler/gravar: nao e seguro prosseguir


class UserDataUnavailable(RuntimeError):
    """Dados do usuario indisponiveis no momento (restauracao falhou)."""


class UserDataManager:
    def __init__(self, bible: BibleRepository, users_dir: Path, turso=None,
                 backup_delay: float = 5.0) -> None:
        self.bible = bible
        self.users_dir = Path(users_dir)
        self.turso = turso
        self.backup_delay = backup_delay
        self._cache: dict[int, tuple[ReadingPlanRepository, StudyRepository]] = {}
        self._locks: dict[int, threading.Lock] = {}
        self._timers: dict[int, threading.Timer] = {}
        self._mutex = threading.RLock()  # protege _cache, _locks e _timers
        self._schema_ready = False
        if turso is not None:
            atexit.register(self.flush)

    # ---- infra ----
    def _db_path(self, user_id: int) -> Path:
        return self.users_dir / f"user_{user_id}.sqlite3"

    def _lock(self, user_id: int) -> threading.Lock:
        with self._mutex:
            return self._locks.setdefault(user_id, threading.Lock())

    def _ensure_schema(self) -> None:
        if self.turso is None or self._schema_ready:
            return
        self.turso.execute(
            """
            CREATE TABLE IF NOT EXISTS user_databases (
                user_id INTEGER PRIMARY KEY,
                data BLOB NOT NULL,
                updated_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._schema_ready = True

    # ---- restauracao ----
    def _restore(self, user_id: int) -> str:
        """Restaura o banco do usuario a partir do Turso. Nunca lanca excecao."""
        if self.turso is None:
            return NO_BACKUP
        try:
            self._ensure_schema()
            res = self.turso.execute("SELECT data FROM user_databases WHERE user_id = ?", [user_id])
            rows = res["rows"]
            if not rows or not rows[0]["data"]:
                return NO_BACKUP
            raw = gzip.decompress(rows[0]["data"])
            self._write_atomic(self._db_path(user_id), raw)
            logger.info("Dados do usuario %s restaurados do Turso (%d bytes).", user_id, len(raw))
            return RESTORED
        except Exception as exc:
            logger.error("Falha ao restaurar usuario %s do Turso: %s", user_id, exc)
            return FAILED

    @staticmethod
    def _write_atomic(path: Path, data: bytes) -> None:
        """Grava via arquivo temporario + rename: nunca deixa um .sqlite3 pela metade."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    # ---- backup ----
    def _snapshot(self, path: Path) -> bytes:
        """Copia consistente do banco (API de backup do SQLite), mesmo com escritas em curso."""
        fd, tmp_name = tempfile.mkstemp(suffix=".sqlite3", dir=self.users_dir)
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            source = sqlite3.connect(path)
            try:
                dest = sqlite3.connect(tmp)
                try:
                    source.backup(dest)
                finally:
                    dest.close()
            finally:
                source.close()
            return tmp.read_bytes()
        finally:
            tmp.unlink(missing_ok=True)

    def backup(self, user_id: int) -> bool:
        """Envia um snapshot ao Turso. So roda para usuarios abertos com seguranca
        (presentes no cache), nunca para um banco que possa ter sido recriado vazio."""
        if self.turso is None:
            return False
        with self._mutex:
            if user_id not in self._cache:
                return False
        path = self._db_path(user_id)
        if not path.exists():
            return False
        with self._lock(user_id):
            try:
                compressed = gzip.compress(self._snapshot(path))
                self._ensure_schema()
                self.turso.execute(
                    """
                    INSERT INTO user_databases (user_id, data, updated_em)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_em = excluded.updated_em
                    """,
                    [user_id, compressed],
                )
                return True
            except Exception as exc:
                logger.error("Falha ao fazer backup do usuario %s no Turso: %s", user_id, exc)
                return False

    def schedule_backup(self, user_id: int) -> None:
        """Agenda backup em segundo plano com debounce: varias escritas seguidas
        (ex.: marcar capitulos em sequencia) geram um unico upload."""
        if self.turso is None or user_id is None:
            return
        with self._mutex:
            if user_id in self._timers:
                return  # ja ha um backup agendado; ele pegara estas escritas tambem
            timer = threading.Timer(self.backup_delay, self._run_scheduled, args=(user_id,))
            timer.daemon = True
            self._timers[user_id] = timer
            timer.start()

    def _run_scheduled(self, user_id: int) -> None:
        with self._mutex:
            self._timers.pop(user_id, None)  # escritas durante o upload agendam um novo
        self.backup(user_id)

    def flush(self) -> None:
        """Executa agora os backups pendentes (usado no encerramento do processo)."""
        with self._mutex:
            pending = list(self._timers.items())
            self._timers.clear()
        for user_id, timer in pending:
            timer.cancel()
            self.backup(user_id)

    # ---- acesso ----
    def get(self, user_id: int) -> tuple[ReadingPlanRepository, StudyRepository]:
        cached = self._cache.get(user_id)
        if cached is not None:
            return cached
        # Abertura serializada por usuario (a restauracao faz I/O de rede e nao
        # deve bloquear os demais usuarios).
        with self._lock(user_id):
            cached = self._cache.get(user_id)
            if cached is not None:
                return cached
            db_path = self._db_path(user_id)
            if self.turso is not None and not db_path.exists():
                if self._restore(user_id) == FAILED:
                    raise UserDataUnavailable(
                        f"Nao foi possivel restaurar os dados do usuario {user_id}."
                    )
            repos = (ReadingPlanRepository(self.bible.books, db_path),
                     StudyRepository(self.bible, db_path))
            with self._mutex:
                self._cache[user_id] = repos
            return repos

    def plans(self, user_id: int) -> ReadingPlanRepository:
        return self.get(user_id)[0]

    def study(self, user_id: int) -> StudyRepository:
        return self.get(user_id)[1]
