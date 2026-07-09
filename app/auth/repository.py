"""Contas de usuario (SQLite proprio, senha com hash).

Isolado das demais tabelas: guarda apenas identidade e credenciais. Os dados
de leitura/estudo de cada usuario ficam num banco separado por conta
(ver UserDataManager), garantindo isolamento total entre usuarios.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
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

        with self._connect() as connection:
            if connection.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                return {"ok": False, "erro": "Este e-mail já está cadastrado."}
            cursor = connection.execute(
                "INSERT INTO users (nome, email, senha_hash) VALUES (?, ?, ?)",
                (nome, email, generate_password_hash(senha)),
            )
            return {"ok": True, "user": {"id": cursor.lastrowid, "nome": nome, "email": email}}

    def authenticate(self, email: str, senha: str) -> dict[str, Any] | None:
        email = (email or "").strip().lower()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row and check_password_hash(row["senha_hash"], senha or ""):
            return {"id": row["id"], "nome": row["nome"], "email": row["email"]}
        return None

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, nome, email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None
