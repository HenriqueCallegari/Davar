"""Protecoes basicas de seguranca: CSRF, limite de tentativas de login,
redirect seguro e cabecalhos HTTP."""
from __future__ import annotations

import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from flask import request, session

CSRF_SESSION_KEY = "_csrf"
CSRF_HEADER = "X-CSRF-Token"
CSRF_FIELD = "csrf_token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# ---- CSRF ------------------------------------------------------------
def csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_is_valid() -> bool:
    """Token do cabecalho (fetch) ou do campo de formulario, comparado ao da sessao."""
    expected = session.get(CSRF_SESSION_KEY)
    sent = request.headers.get(CSRF_HEADER) or request.form.get(CSRF_FIELD) or ""
    return bool(expected) and hmac.compare_digest(str(expected), str(sent))


# ---- redirect seguro ---------------------------------------------------
def safe_next_url(target: str | None) -> str | None:
    """Aceita so caminhos internos. Recusa `//host`, `/\\host` (o navegador
    trata `\\` como `/`), esquemas e caracteres de controle."""
    if not target or not target.startswith("/"):
        return None
    if target.startswith("//") or "\\" in target or any(ord(ch) < 32 for ch in target):
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    return target


# ---- limite de tentativas de login --------------------------------------
class AttemptLimiter:
    """Janela deslizante em memoria: `limit` falhas por `window` segundos por chave.
    Vale por processo; suficiente para frear forca bruta simples."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
            return deque()
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.limit

    def fail(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            self._hits[key].append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


# ---- cabecalhos --------------------------------------------------------
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response
