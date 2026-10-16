"""Rotas do modulo de estudo: grifos, anotacoes, favoritos, colecoes e temas."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from app.core.auth import current_study
from app.core.version import current_bible
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
        memorizar=study.memorize_counts(),
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


@bp.route("/estudo/memorizar")
def memorizar():
    return render_template("pages/memorizar.html", contagem=_study().memorize_counts())


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
MAX_VERSE_NOTE = 5_000
MAX_CHAPTER_NOTE = 10_000
MAX_TAGS = 200
MAX_COLLECTION_NAME = 100
MAX_COLLECTION_DESC = 500
MAX_BATCH = 200


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical_book(abbrev) -> dict | None:
    """Livro do canone (a referencia e identica em qualquer versao)."""
    return current_app.services.bible.get_book(str(abbrev or "").strip())


def _chapter_ref(payload: dict) -> tuple[str, int] | None:
    book = _canonical_book(payload.get("abbrev"))
    capitulo = payload.get("capitulo")
    if book is None or not _is_int(capitulo) or not 1 <= capitulo <= len(book["chapters"]):
        return None
    return book["abbrev"], capitulo


def _ref(payload: dict) -> tuple[str, int, int] | None:
    chapter = _chapter_ref(payload)
    versiculo = payload.get("versiculo")
    if chapter is None or not _is_int(versiculo):
        return None
    abbrev, capitulo = chapter
    total = len(current_app.services.bible.get_chapter(abbrev, capitulo) or [])
    if not 1 <= versiculo <= total:
        return None
    return abbrev, capitulo, versiculo


def _too_long(texto: str, limit: int, what: str):
    if len(texto) > limit:
        return jsonify({"erro": f"{what} pode ter no máximo {limit} caracteres."}), 400
    return None


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
    chapter = _chapter_ref(payload)
    versiculos = payload.get("versiculos")
    if chapter is None or not isinstance(versiculos, list) or not versiculos:
        return jsonify({"erro": "Referência inválida."}), 400
    if len(versiculos) > MAX_BATCH or not all(_is_int(v) for v in versiculos):
        return jsonify({"erro": "Lista de versículos inválida."}), 400
    abbrev, capitulo = chapter
    total = len(current_app.services.bible.get_chapter(abbrev, capitulo) or [])
    versiculos = sorted({v for v in versiculos if 1 <= v <= total})
    if not versiculos:
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


@bp.post("/api/estudo/memorizar")
def api_memorizar():
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    return jsonify(_study().toggle_memorize(*ref))


@bp.get("/api/estudo/memorizar/fila")
def api_memorizar_fila():
    """Cartoes de hoje, com o texto na versao biblica ativa."""
    bible = current_bible()
    cartas = []
    for card in _study().memorize_queue():
        texto = bible.verse_text(card["abbrev"], card["capitulo"], card["versiculo"])
        if not texto:
            continue
        cartas.append({
            **card,
            "texto": texto,
            "referencia": f"{bible.book_name(card['abbrev'])} {card['capitulo']}:{card['versiculo']}",
        })
    return jsonify({"cartas": cartas, **_study().memorize_counts()})


@bp.post("/api/estudo/memorizar/revisar")
def api_memorizar_revisar():
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    try:
        resultado = _study().memorize_review(*ref, str(payload.get("resultado", "")))
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    if resultado is None:
        return jsonify({"erro": "Cartão não encontrado."}), 404
    return jsonify(resultado)


@bp.post("/api/estudo/nota")
def api_nota():
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    texto, tags = str(payload.get("texto", "")), str(payload.get("tags", ""))
    erro = _too_long(texto, MAX_VERSE_NOTE, "A anotação") or _too_long(tags, MAX_TAGS, "As tags")
    if erro:
        return erro
    return jsonify(_study().save_note(*ref, texto, tags))


@bp.post("/api/estudo/reflexao")
def api_reflexao():
    payload = request.get_json(silent=True) or {}
    chapter = _chapter_ref(payload)
    if chapter is None:
        return jsonify({"erro": "Referência inválida."}), 400
    texto = str(payload.get("texto", ""))
    erro = _too_long(texto, MAX_CHAPTER_NOTE, "A reflexão")
    if erro:
        return erro
    return jsonify(_study().save_chapter_note(*chapter, texto))


@bp.post("/api/estudo/colecoes")
def api_criar_colecao():
    payload = request.get_json(silent=True) or {}
    nome = str(payload.get("nome", "")).strip()
    descricao = str(payload.get("descricao", ""))
    if not nome:
        return jsonify({"erro": "Informe um nome para a coleção."}), 400
    erro = (_too_long(nome, MAX_COLLECTION_NAME, "O nome")
            or _too_long(descricao, MAX_COLLECTION_DESC, "A descrição"))
    if erro:
        return erro
    return jsonify(_study().create_collection(nome, descricao))


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
    if not _study().collection_exists(collection_id):
        return jsonify({"erro": "Coleção não encontrada."}), 404
    return jsonify(_study().add_to_collection(collection_id, *ref))


@bp.delete("/api/estudo/colecoes/<int:collection_id>/itens")
def api_remove_item(collection_id: int):
    payload = request.get_json(silent=True) or {}
    ref = _ref(payload)
    if ref is None:
        return jsonify({"erro": "Referência inválida."}), 400
    return jsonify(_study().remove_from_collection(collection_id, *ref))
