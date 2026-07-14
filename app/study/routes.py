"""Rotas do modulo de estudo: grifos, anotacoes, favoritos, colecoes e temas."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from app.core.auth import current_study
from app.study.repository import COLOR_MEANING

bp = Blueprint("study", __name__)


def _study():
    return current_study()


# ---- paginas ---------------------------------------------------------
@bp.route("/estudo")
def hub():
    study = _study()
    return render_template(
        "pages/estudo.html",
        highlights=study.list_highlights(),
        favorites=study.list_favorites(),
        notes=study.list_notes(),
        collections=study.list_collections(),
        cores=COLOR_MEANING,
    )


@bp.route("/estudo/notas")
def notas():
    query = (request.args.get("q") or "").strip()
    return render_template("pages/notas.html", notes=_study().list_notes(query), query=query)


@bp.route("/estudo/colecoes/<int:collection_id>")
def colecao(collection_id: int):
    data = _study().get_collection(collection_id)
    if data is None:
        return render_template("pages/error.html", code=404,
                               mensagem="Coleção não encontrada."), 404
    return render_template("pages/colecao.html", colecao=data)


@bp.route("/estudo/exportar")
def exportar():
    return jsonify(_study().export_all())


@bp.route("/temas")
def temas():
    return render_template("pages/temas.html", temas=current_app.services.themes.list_themes())


@bp.route("/temas/<slug>")
def tema(slug: str):
    data = current_app.services.themes.get_theme(slug)
    if data is None:
        return render_template("pages/error.html", code=404,
                               mensagem="Tema não encontrado."), 404
    return render_template("pages/tema.html", tema=data)


# ---- APIs ------------------------------------------------------------
def _ref(payload: dict) -> tuple[str, int, int] | None:
    abbrev = str(payload.get("abbrev", "")).strip()
    capitulo = payload.get("capitulo")
    versiculo = payload.get("versiculo")
    if not abbrev or not isinstance(capitulo, int) or not isinstance(versiculo, int):
        return None
    return abbrev, capitulo, versiculo


@bp.post("/api/estudo/grifo")
def api_grifo():
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    try:
        resultado = _study().set_highlight(*ref, payload.get("cor"))
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    return jsonify(resultado)


@bp.post("/api/estudo/grifo-lote")
def api_grifo_lote():
    payload = request.get_json(silent=True) or {}
    abbrev = str(payload.get("abbrev", "")).strip()
    capitulo = payload.get("capitulo")
    versiculos = payload.get("versiculos")
    if not abbrev or not isinstance(capitulo, int) or not isinstance(versiculos, list) or not versiculos:
        return jsonify({"erro": "Referência inválida."}), 400
    if not all(isinstance(v, int) for v in versiculos):
        return jsonify({"erro": "Lista de versículos inválida."}), 400
    try:
        resultado = _study().set_highlights_batch(abbrev, capitulo, versiculos, payload.get("cor"))
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    return jsonify(resultado)


@bp.post("/api/estudo/favorito")
def api_favorito():
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    return jsonify(_study().toggle_favorite(*ref))


@bp.post("/api/estudo/nota")
def api_nota():
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    return jsonify(_study().save_note(*ref, str(payload.get("texto", "")), str(payload.get("tags", ""))))


@bp.post("/api/estudo/reflexao")
def api_reflexao():
    payload = request.get_json(silent=True) or {}
    abbrev = str(payload.get("abbrev", "")).strip()
    capitulo = payload.get("capitulo")
    if not abbrev or not isinstance(capitulo, int):
        return jsonify({"erro": "Referência inválida."}), 400
    return jsonify(_study().save_chapter_note(abbrev, capitulo, str(payload.get("texto", ""))))


@bp.post("/api/estudo/colecoes")
def api_criar_colecao():
    payload = request.get_json(silent=True) or {}
    nome = str(payload.get("nome", "")).strip()
    if not nome:
        return jsonify({"erro": "Informe um nome para a coleção."}), 400
    return jsonify(_study().create_collection(nome, str(payload.get("descricao", ""))))


@bp.delete("/api/estudo/colecoes/<int:collection_id>")
def api_apagar_colecao(collection_id: int):
    _study().delete_collection(collection_id)
    return jsonify({"ok": True})


@bp.post("/api/estudo/colecoes/<int:collection_id>/itens")
def api_add_item(collection_id: int):
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    return jsonify(_study().add_to_collection(collection_id, *ref))


@bp.delete("/api/estudo/colecoes/<int:collection_id>/itens")
def api_remove_item(collection_id: int):
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    return jsonify(_study().remove_from_collection(collection_id, *ref))
