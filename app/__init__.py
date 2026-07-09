"""Application factory.

Monta a aplicacao Flask, instancia os repositorios (injetados nos blueprints
via current_app.services) e registra rotas, filtros e handlers de erro.
"""
from __future__ import annotations

from dataclasses import dataclass

from flask import Flask, render_template

from app.bible.repository import BibleRepository
from app.config import Config
from app.core.text import markdown_to_html
from app.plans.repository import ReadingPlanRepository
from app.study.repository import StudyRepository
from app.study.themes import ThemeService


@dataclass
class Services:
    """Container de dependencias compartilhadas (injecao simples)."""

    bible: BibleRepository
    plans: ReadingPlanRepository
    study: StudyRepository
    themes: ThemeService


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object)
    config_object.ensure_dirs()

    bible = BibleRepository(config_object.BIBLE_PATH)
    app.services = Services(
        bible=bible,
        plans=ReadingPlanRepository(bible.books, config_object.DATABASE_PATH),
        study=StudyRepository(bible, config_object.DATABASE_PATH),
        themes=ThemeService(bible, config_object.THEMES_PATH),
    )

    app.jinja_env.filters["markdown"] = markdown_to_html
    _register_blueprints(app)
    _register_shared(app)
    return app


def _register_blueprints(app: Flask) -> None:
    from app.bible.routes import bp as bible_bp
    from app.dashboard.routes import bp as dashboard_bp
    from app.gamification.routes import bp as gamification_bp
    from app.plans.routes import bp as plans_bp
    from app.study.routes import bp as study_bp

    for blueprint in (dashboard_bp, bible_bp, plans_bp, gamification_bp, study_bp):
        app.register_blueprint(blueprint)


def _register_shared(app: Flask) -> None:
    @app.context_processor
    def inject_nav() -> dict:
        return {
            "nav_items": [
                {"endpoint": "dashboard.home", "label": "Início", "icon": "🏠"},
                {"endpoint": "bible.livros", "label": "Bíblia", "icon": "📖"},
                {"endpoint": "plans.listar_planos", "label": "Planos", "icon": "🗓️"},
                {"endpoint": "study.hub", "label": "Estudo", "icon": "✍️"},
                {"endpoint": "study.temas", "label": "Temas", "icon": "🏷️"},
                {"endpoint": "dashboard.crescimento", "label": "Crescimento", "icon": "📈"},
                {"endpoint": "gamification.hub", "label": "Jogos", "icon": "🎮"},
                {"endpoint": "gamification.conquistas", "label": "Conquistas", "icon": "🏆"},
            ]
        }

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("pages/error.html", code=404,
                               mensagem="Página não encontrada."), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("pages/error.html", code=500,
                               mensagem="Algo deu errado. Tente novamente."), 500
