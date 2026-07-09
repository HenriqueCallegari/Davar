"""Helpers de sessao e acesso aos repositorios do usuario logado."""
from __future__ import annotations

from typing import Any

from flask import current_app, session

SESSION_KEY = "user_id"


def login_user(user: dict[str, Any]) -> None:
    session[SESSION_KEY] = user["id"]
    session["user_nome"] = user["nome"]
    session.permanent = True


def logout_user() -> None:
    session.pop(SESSION_KEY, None)
    session.pop("user_nome", None)


def current_user_id() -> int | None:
    return session.get(SESSION_KEY)


def current_user() -> dict[str, Any] | None:
    """Vem da sessao (sem consultar o banco a cada request)."""
    uid = current_user_id()
    if uid is None:
        return None
    return {"id": uid, "nome": session.get("user_nome", "")}


def current_plans():
    return current_app.services.user_data.plans(current_user_id())


def current_study():
    return current_app.services.user_data.study(current_user_id())
