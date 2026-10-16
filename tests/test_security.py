"""Autenticacao, CSRF, limite de tentativas, redirect seguro e SECRET_KEY."""
import os
import unittest
from unittest import mock

from app.config import Config
from app.core.security import safe_next_url

from tests.helpers import api, form_token, make_app, page_token, register


class SecretKeyTests(unittest.TestCase):
    def cfg(self, key):
        return type("C", (Config,), {"SECRET_KEY": key})

    def test_production_requires_key(self):
        with mock.patch.dict(os.environ, {"RENDER": "true"}):
            with self.assertRaises(RuntimeError):
                self.cfg(None).resolve_secret_key()
            with self.assertRaises(RuntimeError):
                self.cfg("bibliakja-dev-key").resolve_secret_key()
            self.assertEqual(self.cfg("k" * 40).resolve_secret_key(), "k" * 40)

    def test_dev_without_key_is_random_per_process(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RENDER", None)
            os.environ.pop("APP_ENV", None)
            os.environ.pop("FLASK_ENV", None)
            self.assertEqual(len(self.cfg(None).resolve_secret_key()), 64)


class SafeNextTests(unittest.TestCase):
    def test_blocks_open_redirects(self):
        for bad in ("//evil.com", "/\\evil.com", "https://evil.com", "evil.com", "/ok\r\nX: y", "", None):
            self.assertIsNone(safe_next_url(bad), bad)
        self.assertEqual(safe_next_url("/planos/1?dia=2"), "/planos/1?dia=2")


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = make_app()

    def client(self):
        return self.app.test_client()

    def test_post_without_csrf_is_rejected(self):
        c = self.client()
        r = c.post("/login", data={"email": "a@a.com", "senha": "x"})
        self.assertEqual(r.status_code, 400)

    def test_register_login_and_session_cookie_flags(self):
        c = self.client()
        r = register(c, email="flags@t.com")
        self.assertEqual(r.status_code, 302)
        cookie = r.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertEqual(c.get("/").status_code, 200)

    def test_short_password_rejected(self):
        r = register(self.client(), email="curta@t.com", senha="1234567")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ao menos 8", r.get_data(as_text=True))

    def test_api_requires_login_with_401_json(self):
        r = self.client().post("/api/estudo/favorito", json={})
        self.assertEqual(r.status_code, 401)
        self.assertIn("login", r.get_json())

    def test_api_requires_csrf_header(self):
        c = self.client()
        register(c, email="csrf@t.com")
        r = c.post("/api/estudo/favorito", json={"abbrev": "jo", "capitulo": 3, "versiculo": 16})
        self.assertEqual(r.status_code, 400)
        ok = api(c, "POST", "/api/estudo/favorito", {"abbrev": "jo", "capitulo": 3, "versiculo": 16})
        self.assertEqual(ok.status_code, 200)

    def test_login_rate_limit(self):
        c = self.client()
        register(c, email="rate@t.com")
        c.get("/sair")
        for _ in range(5):
            r = c.post("/login", data={"email": "rate@t.com", "senha": "errada-errada",
                                       "csrf_token": form_token(c, "/login")})
            self.assertEqual(r.status_code, 200)
        r = c.post("/login", data={"email": "rate@t.com", "senha": "senha-segura-1",
                                   "csrf_token": form_token(c, "/login")})
        self.assertEqual(r.status_code, 429)

    def test_login_clears_old_session_and_logout_clears_all(self):
        c = self.client()
        register(c, email="clear@t.com")
        c.get("/sair")
        with c.session_transaction() as s:
            self.assertNotIn("user_id", s)

    def test_security_headers(self):
        r = self.client().get("/login")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")


class UserDataUnavailableTests(unittest.TestCase):
    def test_503_when_restore_fails(self):
        app, _ = make_app()
        c = app.test_client()
        register(c, email="down@t.com")

        class Down:
            def execute(self, *a, **k):
                raise RuntimeError("down")

        manager = app.services.user_data
        manager.turso = Down()
        manager._cache.clear()
        r = c.get("/planos")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.headers.get("Retry-After"), "30")
        r = c.post("/api/estudo/favorito", json={"abbrev": "jo", "capitulo": 3, "versiculo": 16},
                   headers={"X-CSRF-Token": page_token_safe(c)})
        self.assertEqual(r.status_code, 503)


def page_token_safe(client) -> str:
    # A home depende dos dados do usuario (503); usa o token da propria sessao.
    with client.session_transaction() as s:
        s.setdefault("_csrf", "tok")
        return s["_csrf"]


if __name__ == "__main__":
    unittest.main()
