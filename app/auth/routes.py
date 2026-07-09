"""Rotas de autenticacao: login, registro e logout."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import (
    Blueprint, current_app, redirect, render_template, request, url_for,
)

from app.core.auth import current_user_id, login_user, logout_user

bp = Blueprint("auth", __name__)

LOGIN_VERSE = ("mt", 11, 28)      # Vinde a mim, todos os que estais cansados...
REGISTER_VERSE = ("jr", 29, 11)   # ...pensamentos de paz, e nao de mal...


def _safe_next() -> str | None:
    target = request.args.get("next") or request.form.get("next") or ""
    parsed = urlparse(target)
    if target and not parsed.netloc and not parsed.scheme and target.startswith("/"):
        return target
    return None


def _verse(ref: tuple[str, int, int]) -> dict:
    abbrev, chapter, verse = ref
    bible = current_app.services.bible
    return {
        "texto": bible.verse_text(abbrev, chapter, verse) or "",
        "referencia": f"{bible.book_name(abbrev)} {chapter}:{verse}",
    }


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user_id() is not None:
        return redirect(url_for("dashboard.home"))

    erro = None
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        senha = request.form.get("senha") or ""
        user = current_app.services.auth.authenticate(email, senha)
        if user:
            login_user(user)
            return redirect(_safe_next() or url_for("dashboard.home"))
        erro = "E-mail ou senha incorretos."

    return render_template(
        "auth/login.html",
        versiculo=_verse(LOGIN_VERSE),
        erro=erro,
        email=email,
        next=_safe_next() or "",
    )


@bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if current_user_id() is not None:
        return redirect(url_for("dashboard.home"))

    erro = None
    dados = {"nome": "", "email": ""}
    if request.method == "POST":
        dados["nome"] = (request.form.get("nome") or "").strip()
        dados["email"] = (request.form.get("email") or "").strip()
        senha = request.form.get("senha") or ""
        resultado = current_app.services.auth.create_user(dados["nome"], dados["email"], senha)
        if resultado["ok"]:
            login_user(resultado["user"])
            return redirect(url_for("dashboard.home"))
        erro = resultado["erro"]

    return render_template(
        "auth/registrar.html",
        versiculo=_verse(REGISTER_VERSE),
        erro=erro,
        dados=dados,
    )


@bp.route("/sair")
def sair():
    logout_user()
    return redirect(url_for("auth.login"))
