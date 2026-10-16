"""Jogos gerados do texto biblico, memorizacao (repeticao espacada) e telas novas."""
import random
import unittest
from datetime import timedelta
from unittest import mock

from app.bible.library import BibleLibrary
from app.config import Config
from app.core import clock
from app.gamification import games

from tests.helpers import api, make_app, register

LIB = BibleLibrary(Config.BIBLE_VERSIONS)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.bible = LIB.default

    def test_cloze_reconstructs_original_verse_and_has_valid_options(self):
        for q in games.cloze_questions(self.bible, random.Random(1), 10):
            original = self.bible.verse_text(q["abbrev"], q["capitulo"], q["versiculo"])
            self.assertEqual(q["antes"] + q["correta"] + q["depois"], original)
            self.assertEqual(len(q["opcoes"]), 4)
            self.assertEqual(len(set(o.lower() for o in q["opcoes"])), 4)
            self.assertIn(q["correta"], q["opcoes"])

    def test_scramble_words_join_to_verse(self):
        for q in games.scramble_questions(self.bible, random.Random(2), 6):
            self.assertEqual(" ".join(q["palavras"]), q["texto"])
            self.assertTrue(4 <= len(q["palavras"]) <= 14)

    def test_testament_questions_are_balanced_and_correct(self):
        qs = games.testament_questions(self.bible, random.Random(3), 40)
        self.assertEqual(len(qs), 40)
        answers = {q["correta"] for q in qs}
        self.assertEqual(answers, set(games.TESTAMENTS))
        for q in qs:
            idx = [b["abbrev"] for b in self.bible.books].index(q["abbrev"])
            self.assertEqual(q["correta"], "Antigo Testamento" if idx < 39 else "Novo Testamento")

    def test_pairs_have_distinct_books_and_references(self):
        pairs = games.match_pairs(self.bible, random.Random(4), 6)
        self.assertEqual(len(pairs), 6)
        self.assertEqual(len({p["abbrev"] for p in pairs}), 6)
        self.assertEqual(len({p["referencia"] for p in pairs}), 6)

    def test_scope_restricts_to_chapter_and_seed_is_reproducible(self):
        qs = games.cloze_questions(self.bible, random.Random(5), 5, "jo", 3)
        self.assertTrue(qs)
        self.assertTrue(all(q["abbrev"] == "jo" and q["capitulo"] == 3 for q in qs))
        a = games.cloze_questions(self.bible, random.Random("x"), 5)
        b = games.cloze_questions(self.bible, random.Random("x"), 5)
        self.assertEqual(a, b)

    def test_works_for_every_version(self):
        for meta in LIB.versions:
            repo = LIB.version(meta["id"])
            self.assertTrue(games.cloze_questions(repo, random.Random(6), 5), meta["id"])
            self.assertTrue(games.scramble_questions(repo, random.Random(6), 3), meta["id"])


class GameRoutesAndMemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = make_app()

    def setUp(self):
        self.c = self.app.test_client()
        register(self.c, email=f"g{id(self)}@t.com")

    def get_json(self, url):
        return self.c.get(url).get_json()

    def post(self, url, payload):
        return api(self.c, "POST", url, payload)

    # ---- jogos ----
    def test_hub_and_game_pages_render(self):
        html = self.c.get("/jogos").get_data(as_text=True)
        for text in ("Desafio do dia", "Complete o versículo", "Monte o versículo", "Relâmpago", "Pares", "Quiz de Versículos"):
            self.assertIn(text, html)
        for slug in ("completar", "montar", "relampago", "pares"):
            self.assertEqual(self.c.get(f"/jogos/{slug}").status_code, 200, slug)
        self.assertEqual(self.c.get("/jogos/inexistente").status_code, 404)
        self.assertEqual(self.c.get("/jogos/quiz").status_code, 200)  # rotas antigas continuam

    def test_game_api_shapes_and_limits(self):
        self.assertEqual(len(self.get_json("/api/jogos/completar")["itens"]), 8)
        self.assertEqual(len(self.get_json("/api/jogos/completar?q=999")["itens"]), 15)
        self.assertEqual(len(self.get_json("/api/jogos/pares")["itens"]), 6)
        self.assertEqual(self.c.get("/api/jogos/nada").status_code, 404)

    def test_scope_validation(self):
        itens = self.get_json("/api/jogos/montar?livro=sl&capitulo=23")["itens"]
        self.assertTrue(itens and all(i["abbrev"] == "sl" and i["capitulo"] == 23 for i in itens))
        # livro/capitulo invalidos sao ignorados (cai para a Biblia toda)
        self.assertTrue(self.get_json("/api/jogos/montar?livro=xx&capitulo=1")["itens"])
        html = self.c.get("/jogos/completar?livro=jo&capitulo=3").get_data(as_text=True)
        self.assertIn("João 3", html)

    def test_daily_challenge_is_same_for_everyone_today(self):
        other = self.app.test_client()
        register(other, email=f"o{id(self)}@t.com")
        a = self.get_json("/api/jogos/completar?diario=1")
        b = other.get("/api/jogos/completar?diario=1").get_json()
        self.assertEqual(a["itens"], b["itens"])
        self.assertTrue(a["diario"])
        self.assertNotEqual(a["itens"], self.get_json("/api/jogos/completar")["itens"])

    def test_game_api_requires_login(self):
        self.assertEqual(self.app.test_client().get("/api/jogos/completar").status_code, 401)

    # ---- memorizacao ----
    REF = {"abbrev": "jo", "capitulo": 3, "versiculo": 16}

    def test_toggle_queue_and_review_boxes(self):
        self.assertEqual(self.get_json("/api/estudo/memorizar/fila")["total"], 0)
        self.assertTrue(self.post("/api/estudo/memorizar", self.REF).get_json()["memorizando"])
        fila = self.get_json("/api/estudo/memorizar/fila")
        self.assertEqual((fila["total"], fila["hoje"], len(fila["cartas"])), (1, 1, 1))
        carta = fila["cartas"][0]
        self.assertEqual(carta["referencia"], "João 3:16")
        self.assertIn("Deus", carta["texto"])

        r = self.post("/api/estudo/memorizar/revisar", {**self.REF, "resultado": "lembrei"}).get_json()
        self.assertEqual(r["caixa"], 2)
        self.assertEqual(r["proxima_revisao"], (clock.today() + timedelta(days=3)).isoformat())
        self.assertEqual(self.get_json("/api/estudo/memorizar/fila")["cartas"], [])  # nada mais hoje

        r = self.post("/api/estudo/memorizar/revisar", {**self.REF, "resultado": "esqueci"}).get_json()
        self.assertEqual((r["caixa"], r["proxima_revisao"]), (1, clock.today().isoformat()))
        self.assertEqual(len(self.get_json("/api/estudo/memorizar/fila")["cartas"]), 1)  # volta hoje

        r = self.post("/api/estudo/memorizar/revisar", {**self.REF, "resultado": "quase"}).get_json()
        self.assertEqual(r["proxima_revisao"], (clock.today() + timedelta(days=1)).isoformat())

        self.assertFalse(self.post("/api/estudo/memorizar", self.REF).get_json()["memorizando"])  # remove

    def test_box_is_capped_and_future_cards_are_not_due(self):
        self.post("/api/estudo/memorizar", self.REF)
        for _ in range(8):
            r = self.post("/api/estudo/memorizar/revisar", {**self.REF, "resultado": "lembrei"}).get_json()
        self.assertEqual(r["caixa"], 5)
        self.assertEqual(r["proxima_revisao"], (clock.today() + timedelta(days=30)).isoformat())
        fila = self.get_json("/api/estudo/memorizar/fila")
        self.assertEqual((fila["total"], fila["hoje"]), (1, 0))
        with mock.patch("app.core.clock.now", return_value=clock.now() + timedelta(days=31)):
            self.assertEqual(self.get_json("/api/estudo/memorizar/fila")["hoje"], 1)

    def test_review_validation(self):
        self.assertEqual(self.post("/api/estudo/memorizar/revisar", {**self.REF, "resultado": "x"}).status_code, 400)
        self.assertEqual(self.post("/api/estudo/memorizar/revisar", {**self.REF, "resultado": "lembrei"}).status_code, 404)
        self.assertEqual(self.post("/api/estudo/memorizar", {"abbrev": "jo", "capitulo": 3, "versiculo": 999}).status_code, 400)

    def test_memorize_pages_and_reading_flag(self):
        self.assertIn("Memorizar versículos", self.c.get("/estudo").get_data(as_text=True))
        self.assertEqual(self.c.get("/estudo/memorizar").status_code, 200)
        self.post("/api/estudo/memorizar", self.REF)
        html = self.c.get("/livro/jo/capitulo/3").get_data(as_text=True)
        self.assertIn("is-memo", html)
        self.assertIn("1 cartão espera", self.c.get("/estudo").get_data(as_text=True))

    # ---- leitura e livros ----
    def test_compare_versions_and_practice_links(self):
        html = self.c.get("/livro/jo/capitulo/3").get_data(as_text=True)
        self.assertIn('id="compareBtn"', html)
        self.assertIn("verse__alt", html)
        self.assertIn("NTLH", html)
        self.assertIn("/jogos/completar?livro=jo&amp;capitulo=3", html)
        self.assertIn("/jogos/montar?livro=jo&amp;capitulo=3", html)

    def test_books_grouped_by_category(self):
        html = self.c.get("/livros").get_data(as_text=True)
        for group in ("A Lei", "Históricos", "Poéticos e sabedoria", "Profetas maiores", "Profetas menores",
                      "Evangelhos", "História da Igreja", "Cartas de Paulo", "Cartas gerais", "Profecia"):
            self.assertIn(group, html)
        self.assertEqual(html.count('class="book-card"'), 66)

    def test_read_chapters_are_marked_in_chapter_grid(self):
        self.assertNotIn("is-read", self.c.get("/livro/jo").get_data(as_text=True).split("chapter-grid")[1])
        self.post("/api/leitura/capitulo", {"abbrev": "jo", "capitulo": 3})
        grid = self.c.get("/livro/jo").get_data(as_text=True).split("chapter-grid")[1]
        self.assertEqual(grid.count("is-read"), 1)
        self.assertIn("já lido", grid)


if __name__ == "__main__":
    unittest.main()
