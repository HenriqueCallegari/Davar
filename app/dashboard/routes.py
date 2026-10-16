"""Dashboard espiritual (home) e painel de crescimento."""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, send_from_directory

from app.core import clock
from app.core.auth import current_plans, current_study, current_user
from app.core.version import current_bible

# Convites curtos e gentis para a leitura (um por dia, em rodizio).
CONVITES = (
    "Antes de ler, respire fundo e diga: “Senhor, fala comigo.”",
    "Leia devagar. Que palavra ou frase ficou com você hoje?",
    "Escolha um versículo para levar no dia — e volte a ele à tarde.",
    "Leia em voz alta. A Palavra também foi feita para ser ouvida.",
    "Que tal grifar o que tocou o seu coração?",
    "Sem pressa: um capítulo bem vivido vale mais que cinco corridos.",
    "Anote em uma frase o que Deus falou com você hoje.",
    "Leia pensando em alguém que precisa de uma palavra de ânimo.",
    "Pergunte ao texto: o que isto me ensina sobre Deus?",
    "Termine o dia agradecendo por três coisas.",
    "Releia o versículo do dia antes de dormir.",
    "Leve uma dúvida para a leitura e deixe o texto conversar com ela.",
    "Ouça o capítulo com o botão “Ouvir” enquanto respira com calma.",
    "Ore usando as palavras do salmo que você ler hoje.",
)


def _saudacao(hour: int) -> str:
    if hour < 5:
        return "Boa madrugada"
    if hour < 12:
        return "Bom dia"
    if hour < 18:
        return "Boa tarde"
    return "Boa noite"

bp = Blueprint("dashboard", __name__)


@bp.route("/sw.js")
def service_worker():
    """Servido na raiz para ter escopo sobre todo o site."""
    response = send_from_directory(current_app.static_folder, "sw.js")
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@bp.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(current_app.static_folder, "manifest.webmanifest")


@bp.route("/")
def home():
    now = clock.now()
    seed = now.date().toordinal()
    user = current_user() or {}
    nome = (user.get("nome") or "").strip().split(" ")[0]
    reflexao = current_study().latest_chapter_note()
    if reflexao and len(reflexao["texto"]) > 240:
        reflexao["texto"] = reflexao["texto"][:237].rstrip() + "…"
    return render_template(
        "pages/dashboard.html",
        saudacao=_saudacao(now.hour),
        nome=nome,
        versiculo=current_bible().verse_of_the_day(seed),
        continuar=current_plans().continue_reading(),
        convite=CONVITES[seed % len(CONVITES)],
        reflexao=reflexao,
    )


@bp.route("/crescimento")
def crescimento():
    dados = current_plans().growth_data()
    return render_template("pages/crescimento.html", dados=dados)


@bp.route("/novidades")
def novidades():
    return render_template("pages/novidades.html")


@bp.route("/sobre")
def sobre():
    joao316 = current_app.services.bible.verse_text("jo", 3, 16)
    return render_template("pages/sobre.html", joao316=joao316)
