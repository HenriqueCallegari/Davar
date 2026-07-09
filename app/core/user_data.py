"""Repositorios de dados por usuario (um SQLite local por conta) com
persistencia opcional no Turso via backup/restauracao do arquivo.

Leitura/escrita permanecem locais (rapidas). Quando o Turso esta ativo:
- ao abrir um usuario cujo arquivo local nao existe, restaura do Turso;
- apos escritas, agenda um backup assincrono (arquivo gzip -> blob no Turso).
Isso da persistencia real mesmo no plano free (disco efemero) sem reescrever
as centenas de queries dos repositorios.
"""
from __future__ import annotations

import gzip
import logging
import threading
from pathlib import Path

from app.bible.repository import BibleRepository
from app.plans.repository import ReadingPlanRepository
from app.study.repository import StudyRepository

logger = logging.getLogger(__name__)


class UserDataManager:
    def __init__(self, bible: BibleRepository, users_dir: Path, turso=None) -> None:
        self.bible = bible
        self.users_dir = Path(users_dir)
        self.turso = turso
        self._cache: dict[int, tuple[ReadingPlanRepository, StudyRepository]] = {}
        self._locks: dict[int, threading.Lock] = {}
        self._schema_ready = False

    # ---- infra ----
    def _db_path(self, user_id: int) -> Path:
        return self.users_dir / f"user_{user_id}.sqlite3"

    def _lock(self, user_id: int) -> threading.Lock:
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

    # ---- restauracao / backup ----
    def _restore(self, user_id: int) -> None:
        if self.turso is None:
            return
        self._ensure_schema()
        try:
            res = self.turso.execute("SELECT data FROM user_databases WHERE user_id = ?", [user_id])
            rows = res["rows"]
            if rows and rows[0]["data"]:
                raw = gzip.decompress(rows[0]["data"])
                self._db_path(user_id).write_bytes(raw)
                logger.info("Dados do usuario %s restaurados do Turso (%d bytes).", user_id, len(raw))
        except Exception as exc:  # nunca derruba o app por falha de restauracao
            logger.warning("Falha ao restaurar usuario %s do Turso: %s", user_id, exc)

    def backup(self, user_id: int) -> None:
        if self.turso is None:
            return
        path = self._db_path(user_id)
        if not path.exists():
            return
        with self._lock(user_id):
            try:
                compressed = gzip.compress(path.read_bytes())
                self._ensure_schema()
                self.turso.execute(
                    """
                    INSERT INTO user_databases (user_id, data, updated_em)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_em = excluded.updated_em
                    """,
                    [user_id, compressed],
                )
            except Exception as exc:
                logger.warning("Falha ao fazer backup do usuario %s no Turso: %s", user_id, exc)

    def schedule_backup(self, user_id: int) -> None:
        """Backup em segundo plano (nao bloqueia a resposta)."""
        if self.turso is None or user_id is None:
            return
        threading.Thread(target=self.backup, args=(user_id,), daemon=True).start()

    # ---- acesso ----
    def get(self, user_id: int) -> tuple[ReadingPlanRepository, StudyRepository]:
        if user_id not in self._cache:
            if self.turso is not None and not self._db_path(user_id).exists():
                self._restore(user_id)
            db_path = self._db_path(user_id)
            plans = ReadingPlanRepository(self.bible.books, db_path)
            study = StudyRepository(self.bible, db_path)
            self._cache[user_id] = (plans, study)
        return self._cache[user_id]

    def plans(self, user_id: int) -> ReadingPlanRepository:
        return self.get(user_id)[0]

    def study(self, user_id: int) -> StudyRepository:
        return self.get(user_id)[1]
