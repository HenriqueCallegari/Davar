"""Configuracao central da aplicacao.

Mantem todos os caminhos e ajustes num unico lugar, facilitando deploy,
testes e futura migracao para banco em nuvem / multiplos ambientes.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    """Configuracao base (producao por padrao)."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "bibliakja-dev-key")

    # Dados estaticos
    BIBLE_PATH = Path(os.environ.get("BIBLE_PATH", DATA_DIR / "biblia.json"))
    THEMES_PATH = Path(os.environ.get("THEMES_PATH", DATA_DIR / "themes.json"))
    DEVOTIONALS_PATH = Path(os.environ.get("DEVOTIONALS_PATH", DATA_DIR / "devocionais.json"))

    # Versoes biblicas disponiveis. A primeira com default=True define o canon.
    BIBLE_VERSIONS = [
        {"id": "kja", "nome": "King James Atualizada", "sigla": "KJA",
         "path": DATA_DIR / "biblia.json", "default": True},
        {"id": "ntlh", "nome": "Nova Traducao na Linguagem de Hoje", "sigla": "NTLH",
         "path": DATA_DIR / "ntlh.json"},
    ]
    VERSION_COOKIE = "kja_version"

    # Banco de dados de progresso/estudo. Mantem compatibilidade com a env antiga.
    DATABASE_PATH = Path(
        os.environ.get(
            "READING_PLANS_DB",
            os.environ.get("DATABASE_PATH", INSTANCE_DIR / "bibliakja.sqlite3"),
        )
    )

    # Autenticacao: banco de contas + diretorio com um banco por usuario.
    AUTH_DB = Path(os.environ.get("AUTH_DB", INSTANCE_DIR / "auth.sqlite3"))
    USERS_DIR = Path(os.environ.get("USERS_DIR", INSTANCE_DIR / "users"))

    # Turso (persistencia na nuvem). Se ausente, roda 100% local (efemero no free).
    TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "")
    TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

    @classmethod
    def turso_enabled(cls) -> bool:
        return bool(cls.TURSO_DATABASE_URL and cls.TURSO_AUTH_TOKEN)

    # Estude o Capitulo: sintese teologica original via IA, cacheada globalmente.
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    CHAPTER_STUDY_MODEL = os.environ.get("CHAPTER_STUDY_MODEL", "claude-sonnet-5")
    CHAPTER_STUDY_DB = Path(os.environ.get("CHAPTER_STUDY_DB", INSTANCE_DIR / "chapter_studies.sqlite3"))

    # Regras de negocio
    ANNUAL_PLAN_YEAR = int(os.environ.get("ANNUAL_PLAN_YEAR", "2026"))
    VERSES_PER_MINUTE = 4.8  # ritmo medio de leitura para estimar tempo

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
        cls.USERS_DIR.mkdir(parents=True, exist_ok=True)


class TestConfig(Config):
    TESTING = True
    DATABASE_PATH = Path(os.environ.get("TEST_DATABASE_PATH", INSTANCE_DIR / "test.sqlite3"))
