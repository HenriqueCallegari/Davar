"""Falas de Jesus (letras vermelhas): fichas, divisao do versiculo e telas."""
import json
import unittest

from app.bible.falas import FalasJesus
from app.bible.library import BibleLibrary
from app.config import Config

from tests.helpers import make_app, register

LIB = BibleLibrary(Config.BIBLE_VERSIONS)


class FichasTests(unittest.TestCase):
    def setUp(self):
        self.falas = FalasJesus(mapping={"mt": {"5": ["3-5", "7c"], "6": ["9c2"]}})

    def test_whole_verses_and_ranges(self):
        for verse in (3, 4, 5):
            self.assertEqual(self.falas.parts("mt", 5, verse, "Texto."), [("Texto.", True)])
        self.assertEqual(self.falas.parts("mt", 5, 2, "Texto."), [("Texto.", False)])
        self.assertEqual(self.falas.parts("mt", 9, 1, "Texto."), [("Texto.", False)])
        self.assertEqual(self.falas.parts("MT", 5, 3, "x"), [("x", True)])  # abreviacao sem caixa

    def test_split_after_first_and_second_colon(self):
        self.assertEqual(self.falas.parts("mt", 5, 7, "Ele disse: Pai nosso: que estas"),
                         [("Ele disse: ", False), ("Pai nosso: que estas", True)])
        self.assertEqual(self.falas.parts("mt", 6, 9, "Ele disse: ouvi: Pai nosso"),
                         [("Ele disse: ouvi: ", False), ("Pai nosso", True)])

    def test_dash_after_colon_is_not_red(self):  # NTLH: "Jesus respondeu: — Eu afirmo..."
        parts = self.falas.parts("mt", 5, 7, "Jesus respondeu: — Eu afirmo isto")
        self.assertEqual(parts, [("Jesus respondeu: — ", False), ("Eu afirmo isto", True)])

    def test_missing_colon_does_not_color_narration(self):
        self.assertEqual(self.falas.parts("mt", 5, 7, "So narracao sem dois pontos"),
                         [("So narracao sem dois pontos", False)])
        self.assertEqual(self.falas.parts("mt", 6, 9, "Um so: dois pontos"), [("Um so: dois pontos", False)])

    def test_render_escapes_html(self):
        html = self.falas.render("<b>x</b>: <i>y</i>", "mt", 5, 7)
        self.assertNotIn("<b>", html)
        self.assertIn('<span class="fala-jesus">', html)

    def test_sentence_tokens_stop_the_red_before_the_narration(self):
        falas = FalasJesus(mapping={"mc": {"10": ["52cs", "3s2", "9cs2"]}})
        self.assertEqual(
            falas.parts("mc", 10, 52, "E Jesus lhe disse: Vai, a tua fé te salvou. E logo viu."),
            [("E Jesus lhe disse: ", False), ("Vai, a tua fé te salvou.", True), (" E logo viu.", False)])
        self.assertEqual(falas.parts("mc", 10, 3, "Vai. Volta! E foi embora."),
                         [("Vai. Volta!", True), (" E foi embora.", False)])
        self.assertEqual(falas.parts("mc", 10, 9, "Ele disse: Quem? Eu! E saiu."),
                         [("Ele disse: ", False), ("Quem? Eu!", True), (" E saiu.", False)])

    def test_ntlh_dialogue_with_dashes(self):
        falas = FalasJesus(mapping={"jo": {"9": ["41cs"], "4": ["17c2"], "18": ["5c2s"]}})
        # fala de Jesus com a etiqueta depois, e a continuacao da fala
        self.assertEqual(
            falas.parts("jo", 9, 41, "— Se fossem cegos! — respondeu Jesus. — Mas dizem que veem."),
            [("— ", False), ("Se fossem cegos!", True), (" — respondeu Jesus. — ", False), ("Mas dizem que veem.", True)])
        # menos ':' que o esperado, mas quem fala antes do ultimo ':' e Jesus
        self.assertEqual(
            falas.parts("jo", 4, 17, "— Nao tenho! — disse a mulher. Entao Jesus disse: — Voce acertou."),
            [("— Nao tenho! — disse a mulher. Entao Jesus disse: — ", False), ("Voce acertou.", True)])
        # fala de OUTRA pessoa nao pode ficar vermelha
        self.assertEqual(falas.parts("jo", 18, 5, "— Jesus de Nazare! — responderam. — Sou eu! — disse Jesus."),
                         [("— Jesus de Nazare! — responderam. — Sou eu! — disse Jesus.", False)])

    def test_invalid_token_is_rejected(self):
        with self.assertRaises(ValueError):
            FalasJesus(mapping={"mt": {"1": ["abc"]}})


class DadosReaisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.falas = FalasJesus(Config.FALAS_JESUS_PATH)

    def red(self, abbrev, chapter, verse, version="kja"):
        text = LIB.version(version).verse_text(abbrev, chapter, verse)
        return "".join(t for t, r in self.falas.parts(abbrev, chapter, verse, text) if r)

    def test_known_passages(self):
        self.assertIn("Bem-aventurados os pobres", self.red("mt", 5, 3))
        self.assertTrue(self.red("jo", 3, 16).startswith("Porque Deus amou"))
        self.assertEqual(self.red("mt", 4, 3), "")                 # fala do tentador
        self.assertEqual(self.red("jo", 1, 1), "")                 # narracao
        self.assertEqual(self.red("jo", 3, 4), "")                 # Nicodemos
        self.assertTrue(self.red("mt", 4, 4).startswith("Está escrito"))  # so depois do ':'
        self.assertNotIn("respondendo", self.red("mt", 4, 4))
        self.assertIn("Pai nosso", self.red("mt", 6, 9))
        self.assertTrue(self.red("ap", 22, 12))

    def test_same_map_works_in_ntlh(self):
        text = self.red("jo", 3, 3, "ntlh")
        self.assertTrue(text.startswith("Eu afirmo"), text)   # sem o 'Jesus respondeu: —'
        self.assertNotIn("Jesus respondeu", text)

    def test_every_verse_in_map_exists(self):
        data = json.load(open(Config.FALAS_JESUS_PATH, encoding="utf-8"))
        for abbrev, chapters in data.items():
            book = LIB.default.get_book(abbrev)
            self.assertIsNotNone(book, abbrev)
            for chapter, tokens in chapters.items():
                verses = len(book["chapters"][int(chapter) - 1])
                marks = {}
                for token in tokens:
                    FalasJesus._parse(token, marks)
                self.assertTrue(all(1 <= v <= verses for v in marks), f"{abbrev} {chapter}")

    def test_volume_is_plausible(self):
        # As edicoes de letras vermelhas marcam cerca de 1.900 versiculos.
        self.assertTrue(1500 <= self.falas.total_verses <= 2300, self.falas.total_verses)


class TelasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = make_app()

    def setUp(self):
        self.c = self.app.test_client()
        register(self.c, email=f"f{id(self)}@t.com")

    def test_reading_page_has_red_spans_and_toggle(self):
        html = self.c.get("/livro/mt/capitulo/5").get_data(as_text=True)
        self.assertIn('<span class="fala-jesus">', html)
        self.assertIn("data-toggle-red", html)
        self.assertNotIn('<span class="fala-jesus">', self.c.get("/livro/gn/capitulo/1").get_data(as_text=True))

    def test_other_pages_use_the_filter(self):
        html = self.c.get("/buscar?q=bem-aventurados").get_data(as_text=True)
        self.assertIn('class="fala-jesus"', html)

    def test_memorize_api_returns_parts(self):
        from tests.helpers import api
        api(self.c, "POST", "/api/estudo/memorizar", {"abbrev": "mt", "capitulo": 4, "versiculo": 4})
        carta = self.c.get("/api/estudo/memorizar/fila").get_json()["cartas"][0]
        self.assertEqual([p[1] for p in carta["partes"]], [False, True])
        self.assertEqual("".join(p[0] for p in carta["partes"]), carta["texto"])


if __name__ == "__main__":
    unittest.main()
