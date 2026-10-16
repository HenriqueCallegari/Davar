"""Validacao das APIs de estudo/planos e busca na Biblia."""
import unittest

from app.bible.library import BibleLibrary
from app.bible.repository import normalize
from app.config import Config

from tests.helpers import api, make_app, register


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bible = BibleLibrary(Config.BIBLE_VERSIONS).default

    def test_accent_and_case_insensitive(self):
        self.assertEqual(normalize("Fé EM Cristo"), "fe em cristo")
        a = self.bible.search("fe em")
        b = self.bible.search("FÉ EM")
        self.assertEqual(a["total"], b["total"])
        self.assertGreater(a["total"], 0)

    def test_limit_and_truncation(self):
        r = self.bible.search("amor", limit=5)
        self.assertEqual(len(r["results"]), 5)
        self.assertTrue(r["truncated"])

    def test_keywords_whole_word(self):
        verses = self.bible.collect_by_keywords(["fe"], limit=200)
        self.assertTrue(verses)
        import re
        for v in verses:
            self.assertRegex(normalize(v["text"]), r"\bfe\b")


class ApiValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = make_app()

    def setUp(self):
        self.c = self.app.test_client()
        register(self.c, email=f"v{id(self)}@t.com")

    def post(self, url, payload):
        return api(self.c, "POST", url, payload)

    def test_invalid_references_rejected(self):
        for payload in (
            {"abbrev": "xx", "capitulo": 1, "versiculo": 1},
            {"abbrev": "jo", "capitulo": 999, "versiculo": 1},
            {"abbrev": "jo", "capitulo": 3, "versiculo": 999},
            {"abbrev": "jo", "capitulo": True, "versiculo": 1},
            {"abbrev": "jo", "capitulo": 3, "versiculo": 0},
        ):
            self.assertEqual(self.post("/api/estudo/favorito", payload).status_code, 400, payload)

    def test_valid_reference_uses_canonical_abbrev(self):
        r = self.post("/api/estudo/grifo", {"abbrev": "JO", "capitulo": 3, "versiculo": 16, "cor": "azul"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["abbrev"], "jo")

    def test_batch_limits(self):
        ok = self.post("/api/estudo/grifo-lote", {"abbrev": "jo", "capitulo": 3, "versiculos": [16, 16, 17], "cor": "verde"})
        self.assertEqual(ok.get_json()["versiculos"], [16, 17])
        bad = self.post("/api/estudo/grifo-lote", {"abbrev": "jo", "capitulo": 3, "versiculos": [999], "cor": "verde"})
        self.assertEqual(bad.status_code, 400)
        many = self.post("/api/estudo/grifo-lote", {"abbrev": "jo", "capitulo": 3, "versiculos": list(range(1, 300)), "cor": "verde"})
        self.assertEqual(many.status_code, 400)

    def test_text_length_limits(self):
        ref = {"abbrev": "jo", "capitulo": 3, "versiculo": 16}
        self.assertEqual(self.post("/api/estudo/nota", {**ref, "texto": "x" * 5001}).status_code, 400)
        self.assertEqual(self.post("/api/estudo/nota", {**ref, "texto": "ok"}).status_code, 200)
        self.assertEqual(self.post("/api/estudo/reflexao", {"abbrev": "jo", "capitulo": 3, "texto": "x" * 10001}).status_code, 400)
        self.assertEqual(self.post("/api/estudo/colecoes", {"nome": "n" * 101}).status_code, 400)

    def test_add_item_to_missing_collection_is_404_not_500(self):
        r = self.post("/api/estudo/colecoes/999/itens", {"abbrev": "jo", "capitulo": 3, "versiculo": 16})
        self.assertEqual(r.status_code, 404)

    def test_free_read_endpoint(self):
        r = self.post("/api/leitura/capitulo", {"abbrev": "jo", "capitulo": 3})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["capitulos_lidos"], 1)
        self.assertEqual(self.post("/api/leitura/capitulo", {"abbrev": "jo", "capitulo": 99}).status_code, 404)

    def test_plan_note_validation(self):
        self.assertEqual(self.post("/api/planos/1/dia/99999/nota", {"texto": "x"}).status_code, 404)
        self.assertEqual(self.post("/api/planos/1/dia/1/nota", {"texto": "x" * 10001}).status_code, 400)

    def test_search_pagination_link(self):
        html = self.c.get("/buscar?q=amor").get_data(as_text=True)
        self.assertIn("Mostrar mais resultados", html)
        self.assertEqual(self.c.get("/buscar?q=amor&limite=999999").status_code, 200)

    def test_home_is_welcoming_and_has_no_statistics(self):
        html = self.c.get("/").get_data(as_text=True)
        self.assertIn("Que bom que você veio", html)
        self.assertIn("Um bom começo", html)  # ainda sem leitura: convite, nao numeros
        for dashboardy in ("Capítulos lidos", "Minutos de leitura", "Sequência", "stat-tile"):
            self.assertNotIn(dashboardy, html)
        self.post("/api/planos/1/progresso", {"livro": "Mateus", "capitulo": 1, "concluido": True})
        self.post("/api/estudo/reflexao", {"abbrev": "fp", "capitulo": 4, "texto": "Entreguei a Deus."})
        html = self.c.get("/").get_data(as_text=True)
        self.assertIn("De onde você parou", html)
        self.assertIn("Mateus 2–3", html)
        self.assertIn("Do seu caderno", html)
        self.assertIn("Entreguei a Deus.", html)

    def test_chapters_label_groups_runs(self):
        from app.plans.repository import chapters_label
        rows = [{"livro": "Mateus", "capitulo": n} for n in (28,)] + \
               [{"livro": "Marcos", "capitulo": n} for n in (1, 2, 4)]
        self.assertEqual(chapters_label(rows), "Mateus 28 · Marcos 1–2, 4")

    def test_chapter_grid_marks_available_studies(self):
        html = self.c.get("/livro/jo").get_data(as_text=True)
        self.assertIn("chapter-tile--estudo", html)


if __name__ == "__main__":
    unittest.main()
