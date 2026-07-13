"""Estudo do capitulo: sintese teologica original gerada por IA, com cache global.

O conteudo (resumo, contexto, mensagens-chave e perguntas de reflexao) e uma
SINTESE ORIGINAL produzida por um modelo de linguagem a partir do texto biblico
em si — nunca copia ou parafraseia comentaristas ou obras existentes. O mesmo
conteudo serve a todos os usuarios (nao e por conta), entao e cacheado
globalmente por versao+capitulo para nao gerar (nem pagar) duas vezes.

Sem ANTHROPIC_API_KEY configurada, o recurso informa honestamente que ainda
nao foi ativado, sem quebrar o restante do site.
"""
from __future__ import annotations

import gzip
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Voce e um teologo evangelico, cristao historico e cristocentrico, com \
formacao solida em teologia biblica e coracao de pastor. Seu papel e ajudar o leitor a se \
aprofundar na Palavra de Deus ao ler um capitulo especifico da Biblia.

Escreva uma sintese ORIGINAL (nunca copie ou parafraseie comentaristas especificos ou obras \
existentes), fiel ao texto, cristocentrica, pastoral e acessivel a qualquer leitor — sem jargao \
academico desnecessario, sem polemica denominacional, sem sensacionalismo, sem inventar fatos \
historicos que nao sejam bem estabelecidos. Aponte sempre, quando genuino ao texto, como aquele \
trecho se conecta a pessoa e obra de Jesus Cristo.

Responda SOMENTE com um JSON valido, sem markdown e sem texto fora do JSON, neste formato exato:
{
  "resumo": "2 a 4 paragrafos explicando o que acontece no capitulo",
  "contexto": "1 a 2 paragrafos de contexto historico/literario relevante",
  "mensagens": ["mensagem-chave 1", "mensagem-chave 2", "mensagem-chave 3"],
  "perguntas": ["pergunta de reflexao 1", "pergunta 2", "pergunta 3"]
}"""

CACHE_KEY = "chapter_studies"


class ChapterStudyService:
    def __init__(self, db_path: Path, api_key: str, model: str, turso=None) -> None:
        self.db_path = Path(db_path)
        self.api_key = api_key
        self.model = model
        self.turso = turso
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._restore_from_turso()
        self._initialize()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chapter_studies (
                    version_id TEXT NOT NULL,
                    abbrev TEXT NOT NULL,
                    capitulo INTEGER NOT NULL,
                    conteudo TEXT NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (version_id, abbrev, capitulo)
                )
                """
            )

    # ---- persistencia global no Turso (mesmo padrao do UserDataManager) ----
    def _restore_from_turso(self) -> None:
        if self.turso is None or self.db_path.exists():
            return
        try:
            self.turso.execute(
                "CREATE TABLE IF NOT EXISTS shared_cache (cache_key TEXT PRIMARY KEY, data BLOB NOT NULL)"
            )
            res = self.turso.execute(
                "SELECT data FROM shared_cache WHERE cache_key = ?", [CACHE_KEY]
            )
            if res["rows"] and res["rows"][0]["data"]:
                self.db_path.write_bytes(gzip.decompress(res["rows"][0]["data"]))
                logger.info("Cache de estudos de capitulo restaurado do Turso.")
        except Exception as exc:
            logger.warning("Falha ao restaurar cache de estudos do Turso: %s", exc)

    def _backup_to_turso(self) -> None:
        if self.turso is None or not self.db_path.exists():
            return
        with self._lock:
            try:
                compressed = gzip.compress(self.db_path.read_bytes())
                self.turso.execute(
                    "CREATE TABLE IF NOT EXISTS shared_cache (cache_key TEXT PRIMARY KEY, data BLOB NOT NULL)"
                )
                self.turso.execute(
                    """
                    INSERT INTO shared_cache (cache_key, data) VALUES (?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET data = excluded.data
                    """,
                    [CACHE_KEY, compressed],
                )
            except Exception as exc:
                logger.warning("Falha ao salvar cache de estudos no Turso: %s", exc)

    # ---- acesso ----
    def get_cached(self, version_id: str, abbrev: str, chapter: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT conteudo FROM chapter_studies WHERE version_id = ? AND abbrev = ? AND capitulo = ?",
                (version_id, abbrev, chapter),
            ).fetchone()
        return json.loads(row["conteudo"]) if row else None

    def generate(
        self, version_id: str, abbrev: str, chapter: int, book_name: str, verses: list[str]
    ) -> dict[str, Any]:
        """Retorna do cache, ou gera (via IA), cacheia e retorna a sintese do capitulo."""
        cached = self.get_cached(version_id, abbrev, chapter)
        if cached is not None:
            return {"disponivel": True, **cached}

        if not self.enabled:
            return {
                "disponivel": False,
                "motivo": "Este recurso ainda não foi configurado pelo desenvolvedor.",
            }

        try:
            content = self._call_model(book_name, chapter, verses)
        except Exception as exc:
            logger.error("Falha ao gerar estudo de %s %d: %s", book_name, chapter, exc)
            return {
                "disponivel": False,
                "motivo": "Não foi possível gerar o estudo agora. Tente novamente em instantes.",
            }

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO chapter_studies (version_id, abbrev, capitulo, conteudo)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(version_id, abbrev, capitulo) DO UPDATE SET conteudo = excluded.conteudo
                """,
                (version_id, abbrev, chapter, json.dumps(content, ensure_ascii=False)),
            )
        threading.Thread(target=self._backup_to_turso, daemon=True).start()
        return {"disponivel": True, **content}

    def _call_model(self, book_name: str, chapter: int, verses: list[str]) -> dict[str, Any]:
        import anthropic  # import tardio: so exigido quando a chave esta configurada

        texto = "\n".join(f"{i + 1}. {v}" for i, v in enumerate(verses))
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Livro: {book_name}\nCapítulo: {chapter}\n\nTexto do capítulo:\n{texto}",
                }
            ],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        data = json.loads(raw)
        return {
            "resumo": data.get("resumo", ""),
            "contexto": data.get("contexto", ""),
            "mensagens": data.get("mensagens", []),
            "perguntas": data.get("perguntas", []),
        }
