"""Dashboard espiritual (home) e painel de crescimento."""
from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, render_template, send_from_directory

from app.core.auth import current_plans

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
    overview = current_plans().reading_overview()
    seed = date.today().toordinal()
    versiculo = current_app.services.bible.verse_of_the_day(seed)
    return render_template("pages/dashboard.html", overview=overview, versiculo=versiculo)


@bp.route("/crescimento")
def crescimento():
    dados = current_plans().growth_data()
    return render_template("pages/crescimento.html", dados=dados)


@bp.route("/sobre")
def sobre():
    joao316 = current_app.services.bible.verse_text("jo", 3, 16)
    return render_template("pages/sobre.html", joao316=joao316)
