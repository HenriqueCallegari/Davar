"""Configuracao central da aplicacao.

Mantem todos os caminhos e ajustes num unico lugar, facilitando deploy,
testes e futura migracao para banco em nuvem / multiplos ambientes.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path

# Valor padrao antigo (publico no repositorio): recusado em producao.
LEGACY_DEV_SECRET_KEY = "bibliakja-dev-key"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    """Configuracao base (producao por padrao)."""

    # Cookie de sessao: HttpOnly sempre; Secure so em producao (HTTPS);
    # SameSite=Lax barra o envio do cookie em POSTs de outros sites.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = bool(os.environ.get("RENDER")) or (
        (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "").lower() == "production"
    )
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Tentativas de login: falhas por janela (segundos), por e-mail e por IP.
    LOGIN_MAX_FAILS_PER_EMAIL = 5
    LOGIN_MAX_FAILS_PER_IP = 30
    LOGIN_FAIL_WINDOW = 15 * 60

    # Sem valor padrao publico: ver resolve_secret_key().
    SECRET_KEY = os.environ.get("SECRET_KEY") or None

    # Dados estaticos
    BIBLE_PATH = Path(os.environ.get("BIBLE_PATH", DATA_DIR / "biblia.json"))
    THEMES_PATH = Path(os.environ.get("THEMES_PATH", DATA_DIR / "themes.json"))
    DEVOTIONALS_PATH = Path(os.environ.get("DEVOTIONALS_PATH", DATA_DIR / "devocionais.json"))
    CHAPTER_STUDIES_DIR = Path(os.environ.get("CHAPTER_STUDIES_DIR", DATA_DIR / "estudos"))

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

    # Segundos de debounce antes de enviar o backup de um usuario ao Turso.
    BACKUP_DEBOUNCE_SECONDS = float(os.environ.get("BACKUP_DEBOUNCE_SECONDS", "5"))

    @staticmethod
    def is_production() -> bool:
        """Producao = Render (variavel RENDER) ou APP_ENV/FLASK_ENV=production."""
        env = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "").lower()
        return bool(os.environ.get("RENDER")) or env == "production"

    @classmethod
    def resolve_secret_key(cls) -> str:
        """Chave de assinatura das sessoes.

        Em producao a variavel SECRET_KEY e obrigatoria (e nao pode ser o antigo
        valor padrao publico): sem isso qualquer pessoa forja cookies de sessao.
        Em desenvolvimento, sem SECRET_KEY, usa uma chave aleatoria por processo
        (as sessoes valem ate reiniciar o servidor).
        """
        key = cls.SECRET_KEY
        if cls.is_production() and not getattr(cls, "TESTING", False):
            if not key or key == LEGACY_DEV_SECRET_KEY:
                raise RuntimeError(
                    "SECRET_KEY nao definida (ou insegura) em producao. Defina uma "
                    "chave aleatoria longa, ex.: python -c \"import secrets; "
                    "print(secrets.token_hex(32))\""
                )
            return key
        if not key:
            logging.getLogger(__name__).warning(
                "SECRET_KEY nao definida: usando chave aleatoria so deste processo "
                "(sessoes expiram ao reiniciar). Defina SECRET_KEY para persistir."
            )
            return secrets.token_hex(32)
        return key

    # Fuso usado para datas de leitura/sequencia (o servidor roda em UTC).
    TIMEZONE = os.environ.get("TIMEZONE", "America/Sao_Paulo")

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
