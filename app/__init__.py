"""Application factory.

Monta a aplicacao Flask, instancia os repositorios (injetados nos blueprints
via current_app.services) e registra rotas, filtros e handlers de erro.
"""
from __future__ import annotations

from dataclasses import dataclass

from flask import Flask, redirect, render_template, request, session, url_for

from app.auth.repository import AuthRepository
from app.bible.library import BibleLibrary
from app.bible.repository import BibleRepository
from app.config import Config
from app.core.auth import current_user, current_user_id
from app.core.text import markdown_to_html
from app.core.turso import TursoClient
from app.core.user_data import UserDataManager
from app.core.version import current_version_id
from app.study.themes import ThemeService

# Endpoints acessiveis sem login.
PUBLIC_ENDPOINTS = {
    "auth.login", "auth.registrar", "auth.sair",
    "dashboard.service_worker", "dashboard.manifest",
}


@dataclass
class Services:
    """Container de dependencias compartilhadas (injecao simples)."""

    library: BibleLibrary
    bible: BibleRepository       # versao padrao (canon), leitura global
    themes: ThemeService         # global (somente leitura)
    auth: AuthRepository         # contas
    user_data: UserDataManager   # repositorios por usuario (isolados)


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object)
    config_object.ensure_dirs()

    turso = None
    if config_object.turso_enabled():
        turso = TursoClient(config_object.TURSO_DATABASE_URL, config_object.TURSO_AUTH_TOKEN)

    library = BibleLibrary(config_object.BIBLE_VERSIONS)
    bible = library.default
    app.services = Services(
        library=library,
        bible=bible,
        themes=ThemeService(bible, config_object.THEMES_PATH),
        auth=AuthRepository(sqlite_path=config_object.AUTH_DB, turso=turso),
        user_data=UserDataManager(bible, config_object.USERS_DIR, turso=turso),
    )

    app.jinja_env.filters["markdown"] = markdown_to_html
    _register_blueprints(app)
    _register_shared(app)
    return app


def _register_blueprints(app: Flask) -> None:
    from app.auth.routes import bp as auth_bp
    from app.bible.routes import bp as bible_bp
    from app.dashboard.routes import bp as dashboard_bp
    from app.gamification.routes import bp as gamification_bp
    from app.plans.routes import bp as plans_bp
    from app.study.routes import bp as study_bp

    for blueprint in (auth_bp, dashboard_bp, bible_bp, plans_bp, gamification_bp, study_bp):
        app.register_blueprint(blueprint)


def _register_shared(app: Flask) -> None:
    @app.before_request
    def require_login():
        endpoint = request.endpoint
        if endpoint is None or endpoint == "static" or endpoint in PUBLIC_ENDPOINTS:
            return None
        if session.get("user_id") is None:
            return redirect(url_for("auth.login", next=request.path))
        return None

    @app.after_request
    def sync_after_write(response):
        # Backup assincrono no Turso apos escritas bem-sucedidas do usuario.
        try:
            uid = current_user_id()
            if (uid is not None and request.method in ("POST", "DELETE")
                    and request.path.startswith("/api/") and response.status_code < 400):
                app.services.user_data.schedule_backup(uid)
        except Exception:
            pass
        return response

    @app.context_processor
    def inject_user() -> dict:
        return {"current_user": current_user()}

    @app.context_processor
    def inject_versions() -> dict:
        return {
            "bible_versions": app.services.library.versions,
            "current_version": current_version_id(),
        }

    @app.context_processor
    def inject_nav() -> dict:
        return {
            "nav_items": [
                {"endpoint": "dashboard.home", "label": "Início"},
                {"endpoint": "bible.livros", "label": "Bíblia"},
                {"endpoint": "plans.listar_planos", "label": "Planos"},
                {"endpoint": "study.hub", "label": "Estudo"},
                {"endpoint": "study.temas", "label": "Temas"},
                {"endpoint": "dashboard.crescimento", "label": "Crescimento"},
                {"endpoint": "gamification.hub", "label": "Jogos"},
                {"endpoint": "gamification.conquistas", "label": "Conquistas"},
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
