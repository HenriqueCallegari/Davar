"""Rotas dos planos de leitura, progresso, notas e estatisticas."""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from app.core.auth import current_plans

bp = Blueprint("plans", __name__)

MAX_NOTE_LENGTH = 10_000


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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

    if not livro or not _is_int(capitulo):
        return jsonify({"erro": "Dados inválidos para atualizar o progresso."}), 400

    resultado = current_plans().update_progress(plano_id, livro, capitulo, concluido)
    if resultado is None:
        return jsonify({"erro": "Capítulo do plano não encontrado."}), 404
    return jsonify(resultado)


@bp.post("/api/leitura/capitulo")
def registrar_leitura_livre():
    """Capitulo lido fora de um plano: entra em sequencia, heatmap e conquistas."""
    payload = request.get_json(silent=True) or {}
    abbrev = str(payload.get("abbrev", "")).strip()
    capitulo = payload.get("capitulo")
    if not abbrev or not _is_int(capitulo):
        return jsonify({"erro": "Referência inválida."}), 400
    resultado = current_plans().mark_chapter_read(abbrev, capitulo)
    if resultado is None:
        return jsonify({"erro": "Capítulo não encontrado."}), 404
    return jsonify(resultado)


@bp.post("/api/planos/<int:plano_id>/dia/<int:dia>/nota")
def salvar_nota(plano_id: int, dia: int):
    payload = request.get_json(silent=True) or {}
    texto = str(payload.get("texto", ""))
    if len(texto) > MAX_NOTE_LENGTH:
        return jsonify({"erro": f"A anotação pode ter no máximo {MAX_NOTE_LENGTH} caracteres."}), 400
    resultado = current_plans().save_note(plano_id, dia, texto)
    if resultado is None:
        return jsonify({"erro": "Plano ou dia não encontrado."}), 404
    return jsonify(resultado)
