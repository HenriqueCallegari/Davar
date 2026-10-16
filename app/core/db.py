"""Conexao SQLite padrao dos repositorios por usuario.

- WAL: leitores nao bloqueiam o escritor (varios requests + thread de backup).
- busy_timeout: espera o lock em vez de falhar com "database is locked".
- `with connect(path) as conn:` faz commit/rollback E FECHA a conexao
  (o `with` padrao do sqlite3 so faz commit, deixando a conexao aberta).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

BUSY_TIMEOUT_MS = 10_000


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(db_path: Path | str) -> sqlite3.Connection:
    connection = sqlite3.connect(
        db_path, timeout=BUSY_TIMEOUT_MS / 1000, factory=_ClosingConnection
    )
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
