"""Contas de usuario. Persistidas no Turso (se configurado) ou em SQLite local.

O dialeto do Turso e SQLite, portanto o mesmo SQL atende aos dois backends;
apenas a execucao muda (ver _query).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthRepository:
    def __init__(self, sqlite_path: Path | None = None, turso=None) -> None:
        self.turso = turso
        self.sqlite_path = Path(sqlite_path) if sqlite_path else None
        self._initialize()

    def _query(self, sql: str, args: tuple = (), fetch: bool = False) -> Any:
        if self.turso is not None:
            res = self.turso.execute(sql, list(args))
            return res["rows"] if fetch else res
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.execute(sql, args)
            if fetch:
                rows = [dict(r) for r in cursor.fetchall()]
                connection.commit()
                return rows
            connection.commit()
            return {"rows": [], "last_insert_rowid": cursor.lastrowid, "affected": cursor.rowcount}
        finally:
            connection.close()

    def _initialize(self) -> None:
        self._query(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def create_user(self, nome: str, email: str, senha: str) -> dict[str, Any]:
        nome = (nome or "").strip()
        email = (email or "").strip().lower()
        if len(nome) < 2:
            return {"ok": False, "erro": "Informe seu nome."}
        if not EMAIL_RE.match(email):
            return {"ok": False, "erro": "Informe um e-mail válido."}
        if len(senha or "") < 6:
            return {"ok": False, "erro": "A senha precisa ter ao menos 6 caracteres."}

        existing = self._query("SELECT id FROM users WHERE email = ?", (email,), fetch=True)
        if existing:
            return {"ok": False, "erro": "Este e-mail já está cadastrado."}

        result = self._query(
            "INSERT INTO users (nome, email, senha_hash) VALUES (?, ?, ?)",
            (nome, email, generate_password_hash(senha)),
        )
        user_id = result.get("last_insert_rowid")
        if not user_id:  # fallback (alguns backends nao retornam rowid no insert)
            row = self._query("SELECT id FROM users WHERE email = ?", (email,), fetch=True)
            user_id = row[0]["id"] if row else None
        return {"ok": True, "user": {"id": user_id, "nome": nome, "email": email}}

    def authenticate(self, email: str, senha: str) -> dict[str, Any] | None:
        email = (email or "").strip().lower()
        rows = self._query("SELECT * FROM users WHERE email = ?", (email,), fetch=True)
        if rows and check_password_hash(rows[0]["senha_hash"], senha or ""):
            row = rows[0]
            return {"id": row["id"], "nome": row["nome"], "email": row["email"]}
        return None

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        rows = self._query("SELECT id, nome, email FROM users WHERE id = ?", (user_id,), fetch=True)
        return rows[0] if rows else None
