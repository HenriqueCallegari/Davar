"""Rotas de jogos, quiz e conquistas."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from app.core.auth import current_plans
from app.gamification.quiz import build_questions

bp = Blueprint("gamification", __name__)


@bp.route("/jogos")
def hub():
    return render_template("pages/jogos.html")


@bp.route("/jogos/quiz")
def quiz():
    return render_template("pages/quiz.html")


@bp.route("/jogos/ordenar")
def ordenar():
    bible = current_app.services.bible
    return render_template("pages/ordenar.html", livros=[b["name"] for b in bible.books])


@bp.route("/conquistas")
def conquistas():
    dados = current_plans().get_achievements()
    return render_template("pages/conquistas.html", **dados)


@bp.get("/api/quiz")
def api_quiz():
    quantidade = request.args.get("q", default=10, type=int) or 10
    quantidade = max(1, min(quantidade, 20))
    perguntas = build_questions(current_app.services.bible, quantidade)
    return jsonify({"perguntas": perguntas})
