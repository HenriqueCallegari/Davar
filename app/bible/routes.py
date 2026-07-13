"""Rotas do texto biblico: catalogo, leitura, busca global e troca de versao."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, make_response, redirect, render_template, request, url_for

from app.config import Config
from app.core.auth import current_study
from app.core.version import current_bible, current_version_id

bp = Blueprint("bible", __name__)


def _safe_next(default_endpoint: str = "dashboard.home") -> str:
    """Evita open-redirect: so aceita caminhos internos."""
    target = request.args.get("next", "")
    parsed = urlparse(target)
    if target and not parsed.netloc and not parsed.scheme and target.startswith("/"):
        return target
    return url_for(default_endpoint)


@bp.route("/versao/<version_id>")
def trocar_versao(version_id: str):
    library = current_app.services.library
    destino = _safe_next()
    response = make_response(redirect(destino))
    if library.has(version_id):
        response.set_cookie(
            Config.VERSION_COOKIE, version_id,
            max_age=60 * 60 * 24 * 365, samesite="Lax",
        )
    return response


@bp.route("/livros")
def livros():
    bible = current_bible()
    return render_template("pages/livros.html", livros=bible.book_summaries())


@bp.route("/livro/<abbrev>")
def capitulos(abbrev: str):
    bible = current_bible()
    book = bible.get_book(abbrev)
    if not book:
        return render_template("pages/error.html", code=404,
                               mensagem="Livro não encontrado."), 404
    return render_template(
        "pages/capitulos.html",
        abbrev=book["abbrev"],
        name=book["name"],
        total=len(book["chapters"]),
    )


@bp.route("/livro/<abbrev>/capitulo/<int:num>")
def capitulo(abbrev: str, num: int):
    bible = current_bible()
    study = current_study()
    book = bible.get_book(abbrev)
    if not book:
        return render_template("pages/error.html", code=404,
                               mensagem="Livro não encontrado."), 404
    verses = bible.get_chapter(abbrev, num)
    if verses is None:
        return render_template("pages/error.html", code=404,
                               mensagem="Capítulo não encontrado."), 404

    marks = study.chapter_marks(book["abbrev"], num)
    verse_rows = [
        {
            "n": index,
            "text": text,
            "cor": marks["highlights"].get(index),
            "favorito": index in marks["favorites"],
            "nota": marks["notes"].get(index, {}).get("texto", ""),
        }
        for index, text in enumerate(verses, start=1)
    ]

    return render_template(
        "pages/leitura.html",
        abbrev=book["abbrev"],
        name=book["name"],
        num=num,
        verses=verse_rows,
        navigation=bible.chapter_navigation(abbrev, num),
        plano_id=request.args.get("plano", type=int),
    )


@bp.get("/api/estudo-capitulo/<abbrev>/<int:num>")
def api_estudo_capitulo(abbrev: str, num: int):
    bible = current_bible()
    book = bible.get_book(abbrev)
    if not book:
        return jsonify({"disponivel": False, "motivo": "Livro não encontrado."}), 404
    verses = bible.get_chapter(abbrev, num)
    if verses is None:
        return jsonify({"disponivel": False, "motivo": "Capítulo não encontrado."}), 404

    resultado = current_app.services.chapter_study.generate(
        current_version_id(), book["abbrev"], num, book["name"], verses
    )
    return jsonify(resultado)


@bp.route("/buscar")
def buscar():
    bible = current_bible()
    query = (request.args.get("q") or "").strip()
    testament = request.args.get("testamento") or None
    abbrev = request.args.get("livro") or None

    resultado = bible.search(query, testament=testament, abbrev=abbrev) if query else None
    return render_template(
        "pages/busca.html",
        query=query,
        testamento=testament,
        livro=abbrev,
        livros=bible.book_summaries(),
        resultado=resultado,
    )
