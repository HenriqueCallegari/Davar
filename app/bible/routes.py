"""Rotas do texto biblico: catalogo, leitura, busca global e troca de versao."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, make_response, redirect, render_template, request, url_for

from app.config import Config
from app.core.auth import current_plans, current_study
from app.core.security import safe_next_url
from app.core.version import current_bible, current_version_id

bp = Blueprint("bible", __name__)

# Grupos tradicionais dos livros (indices no canone de 66 livros): testamento,
# nome do grupo, cor do design system, intervalo [inicio, fim).
GRUPOS_LIVROS = (
    ("Antigo Testamento", "A Lei", "amarelo", 0, 5),
    ("Antigo Testamento", "Históricos", "azul", 5, 17),
    ("Antigo Testamento", "Poéticos e sabedoria", "roxo", 17, 22),
    ("Antigo Testamento", "Profetas maiores", "vermelho", 22, 27),
    ("Antigo Testamento", "Profetas menores", "verde", 27, 39),
    ("Novo Testamento", "Evangelhos", "amarelo", 39, 43),
    ("Novo Testamento", "História da Igreja", "azul", 43, 44),
    ("Novo Testamento", "Cartas de Paulo", "roxo", 44, 57),
    ("Novo Testamento", "Cartas gerais", "verde", 57, 65),
    ("Novo Testamento", "Profecia", "vermelho", 65, 66),
)

SEARCH_PAGE_SIZE = 200
SEARCH_MAX_RESULTS = 1000


def _safe_next(default_endpoint: str = "dashboard.home") -> str:
    """Evita open-redirect: so aceita caminhos internos."""
    return safe_next_url(request.args.get("next")) or url_for(default_endpoint)


@bp.route("/versao/<version_id>")
def trocar_versao(version_id: str):
    library = current_app.services.library
    destino = _safe_next()
    response = make_response(redirect(destino))
    if library.has(version_id):
        response.set_cookie(
            Config.VERSION_COOKIE, version_id,
            max_age=60 * 60 * 24 * 365, samesite="Lax", httponly=True,
            secure=current_app.config["SESSION_COOKIE_SECURE"],
        )
    return response


@bp.route("/livros")
def livros():
    summaries = current_bible().book_summaries()
    testamentos: dict[str, list[dict]] = {}
    for testamento, nome, cor, inicio, fim in GRUPOS_LIVROS:
        livros = summaries[inicio:fim]
        if livros:
            testamentos.setdefault(testamento, []).append({"nome": nome, "cor": cor, "livros": livros})
    return render_template("pages/livros.html", testamentos=testamentos)


@bp.route("/livro/<abbrev>")
def capitulos(abbrev: str):
    bible = current_bible()
    book = bible.get_book(abbrev)
    if not book:
        return render_template("pages/error.html", code=404,
                               mensagem="Livro não encontrado."), 404
    estudos = current_app.services.chapter_study
    total = len(book["chapters"])
    return render_template(
        "pages/capitulos.html",
        abbrev=book["abbrev"],
        name=book["name"],
        total=total,
        com_estudo={n for n in range(1, total + 1) if estudos.get(book["abbrev"], n)},
        lidos=current_plans().read_chapters_of_book(book["abbrev"]),
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
    # Segunda versao (a primeira diferente da ativa) para a leitura comparada.
    library = current_app.services.library
    outras = [v for v in library.versions if v["id"] != current_version_id()]
    alt_meta = outras[0] if outras else None
    alt_verses = library.version(alt_meta["id"]).get_chapter(abbrev, num) or [] if alt_meta else []
    verse_rows = [
        {
            "n": index,
            "text": text,
            "cor": marks["highlights"].get(index),
            "favorito": index in marks["favorites"],
            "memorizando": index in marks["memorize"],
            "nota": marks["notes"].get(index, {}).get("texto", ""),
            "alt": alt_verses[index - 1] if index <= len(alt_verses) else "",
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
        reflexao=study.get_chapter_note(book["abbrev"], num),
        alt_sigla=alt_meta["sigla"] if alt_meta and alt_verses else None,
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

    limite = request.args.get("limite", default=SEARCH_PAGE_SIZE, type=int)
    limite = max(SEARCH_PAGE_SIZE, min(limite, SEARCH_MAX_RESULTS))

    resultado = bible.search(query, testament=testament, abbrev=abbrev, limit=limite) if query else None
    return render_template(
        "pages/busca.html",
        limite=limite,
        proximo_limite=min(limite + SEARCH_PAGE_SIZE, SEARCH_MAX_RESULTS),
        limite_max=SEARCH_MAX_RESULTS,
        query=query,
        testamento=testament,
        livro=abbrev,
        livros=bible.book_summaries(),
        resultado=resultado,
    )
