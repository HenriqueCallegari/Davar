"""Rotas do texto biblico: catalogo, leitura e busca global."""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

bp = Blueprint("bible", __name__)


@bp.route("/livros")
def livros():
    bible = current_app.services.bible
    return render_template("pages/livros.html", livros=bible.book_summaries())


@bp.route("/livro/<abbrev>")
def capitulos(abbrev: str):
    bible = current_app.services.bible
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
    bible = current_app.services.bible
    study = current_app.services.study
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


@bp.route("/buscar")
def buscar():
    bible = current_app.services.bible
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
