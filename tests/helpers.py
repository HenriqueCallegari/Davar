"""Utilitarios de teste: app Flask isolada em diretorio temporario."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from app import create_app
from app.config import Config


def make_app(**overrides):
    tmp = Path(tempfile.mkdtemp(prefix="davar_test_"))
    attrs = {
        "TESTING": True,
        "AUTH_DB": tmp / "auth.sqlite3",
        "USERS_DIR": tmp / "users",
        "TURSO_DATABASE_URL": "",
        "TURSO_AUTH_TOKEN": "",
        "SECRET_KEY": "x" * 40,
        **overrides,
    }
    return create_app(type("TestCfg", (Config,), attrs)), tmp


def form_token(client, path: str) -> str:
    """Token CSRF do campo oculto de um formulario (login/registro)."""
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def page_token(client) -> str:
    """Token CSRF da meta tag das paginas autenticadas (usado pelo fetch)."""
    html = client.get("/").get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def register(client, email="t@t.com", senha="senha-segura-1", nome="Teste"):
    return client.post("/registrar", data={
        "nome": nome, "email": email, "senha": senha,
        "csrf_token": form_token(client, "/registrar"),
    })


def api(client, method, url, payload=None):
    return client.open(url, method=method, json=payload or {},
                       headers={"X-CSRF-Token": page_token(client)})
