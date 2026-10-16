"""Rotas de jogos, quiz e conquistas."""
from __future__ import annotations

import random

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from app.core import clock
from app.core.auth import current_plans
from app.core.version import current_bible
from app.gamification import games
from app.gamification.quiz import build_questions

bp = Blueprint("gamification", __name__)

# slug -> dados da pagina e do gerador. Todos usam o texto da Biblia na versao ativa.
JOGOS = {
    "completar": {
        "titulo": "Complete o versículo",
        "eyebrow": "Memória",
        "descricao": "Uma palavra sumiu do versículo. Qual é a certa?",
        "padrao": 8, "maximo": 15, "escopo": True,
        "gerador": games.cloze_questions,
    },
    "montar": {
        "titulo": "Monte o versículo",
        "eyebrow": "Quebra-cabeça",
        "descricao": "As palavras estão embaralhadas. Toque nelas na ordem certa.",
        "padrao": 5, "maximo": 10, "escopo": True,
        "gerador": games.scramble_questions,
    },
    "relampago": {
        "titulo": "Relâmpago",
        "eyebrow": "Reflexo",
        "descricao": "Antigo ou Novo Testamento? Responda o máximo que puder antes do tempo acabar.",
        "padrao": 40, "maximo": 80, "escopo": False,
        "gerador": games.testament_questions,
    },
    "pares": {
        "titulo": "Pares",
        "eyebrow": "Memória visual",
        "descricao": "Vire as cartas e combine cada trecho com a sua referência.",
        "padrao": 6, "maximo": 8, "escopo": False,
        "gerador": games.match_pairs,
    },
}


@bp.route("/jogos")
def hub():
    return render_template("pages/jogos.html", jogos=JOGOS)


@bp.route("/jogos/quiz")
def quiz():
    return render_template("pages/quiz.html")


@bp.route("/jogos/ordenar")
def ordenar():
    bible = current_app.services.bible
    return render_template("pages/ordenar.html", livros=[b["name"] for b in bible.books])


@bp.route("/jogos/<slug>")
def jogo(slug: str):
    meta = JOGOS.get(slug)
    if meta is None:
        abort(404)
    escopo = _escopo() if meta["escopo"] else None
    return render_template(
        "pages/jogo.html", slug=slug, jogo=meta, escopo=escopo,
        diario=bool(request.args.get("diario")) and meta["escopo"],
    )


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


@bp.get("/api/jogos/<slug>")
def api_jogo(slug: str):
    meta = JOGOS.get(slug)
    if meta is None:
        return jsonify({"erro": "Jogo não encontrado."}), 404
    quantidade = request.args.get("q", default=meta["padrao"], type=int) or meta["padrao"]
    quantidade = max(1, min(quantidade, meta["maximo"]))

    diario = bool(request.args.get("diario")) and meta["escopo"]
    # Desafio do dia: mesma semente para todos no mesmo dia (e versao biblica).
    rng = random.Random(f"{slug}:{clock.today().isoformat()}") if diario else random.Random()

    bible = current_bible()
    kwargs = {}
    if meta["escopo"]:
        escopo = _escopo()
        if escopo:
            kwargs = {"abbrev": escopo["abbrev"], "chapter": escopo["capitulo"]}
    itens = meta["gerador"](bible, rng, quantidade, **kwargs) if slug != "pares" else \
        meta["gerador"](bible, rng, quantidade)
    return jsonify({"itens": itens, "diario": diario})


def _escopo() -> dict | None:
    """Livro/capitulo pedidos na URL (?livro=jo&capitulo=3), validados contra o canone."""
    book = current_app.services.bible.get_book(request.args.get("livro", "").strip())
    if book is None:
        return None
    capitulo = request.args.get("capitulo", type=int)
    if capitulo is not None and not 1 <= capitulo <= len(book["chapters"]):
        capitulo = None
    rotulo = book["name"] + (f" {capitulo}" if capitulo else "")
    return {"abbrev": book["abbrev"], "capitulo": capitulo, "rotulo": rotulo}
