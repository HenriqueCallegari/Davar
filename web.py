"""Ponto de entrada WSGI.

O Render executa `gunicorn web:app`, portanto este modulo apenas expoe `app`.
Toda a montagem esta em app/__init__.py (application factory).
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
