"""Rotas dos planos de leitura, progresso, notas e estatisticas."""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from app.core.auth import current_plans

bp = Blueprint("plans", __name__)


@bp.route("/planos")
def listar_planos():
    planos = current_plans().list_plans()
    return render_template("pages/planos.html", planos=planos)


@bp.route("/planos/<int:plano_id>")
def mostrar_plano(plano_id: int):
    dia = request.args.get("dia", type=int)
    dados = current_plans().get_plan_day(plano_id, dia)
    if dados is None:
        return render_template("pages/error.html", code=404,
                               mensagem="Plano não encontrado."), 404
    return render_template("pages/plano.html", **dados)


@bp.route("/planos/<int:plano_id>/estatisticas")
def mostrar_estatisticas(plano_id: int):
    dados = current_plans().get_statistics_page(plano_id)
    if dados is None:
        return render_template("pages/error.html", code=404,
                               mensagem="Plano não encontrado."), 404
    return render_template("pages/estatisticas.html", **dados)


@bp.post("/api/planos/<int:plano_id>/progresso")
def salvar_progresso(plano_id: int):
    payload = request.get_json(silent=True) or {}
    livro = str(payload.get("livro", "")).strip()
    capitulo = payload.get("capitulo")
    concluido = bool(payload.get("concluido"))

    if not livro or not isinstance(capitulo, int):
        return jsonify({"erro": "Dados inválidos para atualizar o progresso."}), 400

    resultado = current_plans().update_progress(plano_id, livro, capitulo, concluido)
    if resultado is None:
        return jsonify({"erro": "Capítulo do plano não encontrado."}), 404
    return jsonify(resultado)


@bp.post("/api/planos/<int:plano_id>/dia/<int:dia>/nota")
def salvar_nota(plano_id: int, dia: int):
    payload = request.get_json(silent=True) or {}
    texto = str(payload.get("texto", ""))
    resultado = current_plans().save_note(plano_id, dia, texto)
    if resultado is None:
        return jsonify({"erro": "Plano não encontrado."}), 404
    return jsonify(resultado)
