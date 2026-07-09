"""Resolucao da versao biblica ativa (por cookie, com fallback para o padrao)."""
from __future__ import annotations

from flask import current_app, request

from app.config import Config


def current_version_id() -> str:
    library = current_app.services.library
    vid = request.cookies.get(Config.VERSION_COOKIE)
    return vid if vid and library.has(vid) else library.default_id


def current_bible():
    return current_app.services.library.version(current_version_id())
