"""Planos de leitura: contagem sem duplicar, leitura livre e migracao do cronograma."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.bible.library import BibleLibrary
from app.config import Config
from app.core.db import connect
from app.plans.repository import ReadingPlanRepository

BOOKS = BibleLibrary(Config.BIBLE_VERSIONS).default.books


def repo():
    return ReadingPlanRepository(BOOKS, Path(tempfile.mkdtemp()) / "u.sqlite3")


class PlansTests(unittest.TestCase):
    def test_chapter_in_two_plans_counts_once(self):
        plans = repo()
        # Mateus 1 existe no plano 1 (NT) e no plano 3 (Porcao Diaria).
        for plan_id in (1, 3):
            self.assertIsNotNone(plans.update_progress(plan_id, "Mateus", 1, True))
        overview = plans.reading_overview()
        self.assertEqual(overview["capitulos_lidos"], 1)
        self.assertEqual(overview["versiculos_lidos"], len(BOOKS[39]["chapters"][0]))

    def test_free_read_counts_streak_and_achievement(self):
        plans = repo()
        result = plans.mark_chapter_read("JO", 3)  # abreviacao em qualquer caixa
        self.assertEqual(result["capitulos_lidos"], 1)
        self.assertIn("primeiro_capitulo", [a["codigo"] for a in result["new_achievements"]])
        self.assertEqual(plans.reading_overview()["sequencia_atual"], 1)
        plans.mark_chapter_read("jo", 3)  # repetir nao duplica
        self.assertEqual(plans.reading_overview()["capitulos_lidos"], 1)
        self.assertIsNone(plans.mark_chapter_read("xx", 1))
        self.assertIsNone(plans.mark_chapter_read("jo", 999))

    def test_schedule_change_preserves_progress(self):
        path = Path(tempfile.mkdtemp()) / "u.sqlite3"
        plans = ReadingPlanRepository(BOOKS, path)
        plans.update_progress(1, "Mateus", 1, True)
        plans.update_progress(1, "Mateus", 2, True)
        plans.save_note(1, 1, "nota do dia 1")
        # Simula cronograma antigo/diferente: assinatura divergente forca a reconstrucao.
        with connect(path) as conn:
            conn.execute("UPDATE reading_plans SET assinatura = 'antiga' WHERE id = 1")
        again = ReadingPlanRepository(BOOKS, path)
        day = again.get_plan_day(1, 1)
        self.assertEqual(sum(c["concluido"] for c in day["chapters"]), 2)
        self.assertEqual(day["note"], "nota do dia 1")
        self.assertEqual(again.get_plan_day(1, 1)["progress"]["completed_chapters"], 2)

    def test_legacy_db_without_signature_column_is_migrated(self):
        path = Path(tempfile.mkdtemp()) / "u.sqlite3"
        plans = ReadingPlanRepository(BOOKS, path)
        plans.update_progress(2, "Gênesis", 1, True)
        with connect(path) as conn:
            conn.execute("ALTER TABLE reading_plans DROP COLUMN assinatura")
        again = ReadingPlanRepository(BOOKS, path)
        self.assertEqual(again.get_plan_day(2, 1)["progress"]["completed_chapters"], 1)

    def test_note_day_out_of_range(self):
        plans = repo()
        self.assertIsNone(plans.save_note(1, 0, "x"))
        self.assertIsNone(plans.save_note(1, 10_000, "x"))
        self.assertIsNotNone(plans.save_note(1, 1, "x"))

    def test_connections_use_wal(self):
        path = Path(tempfile.mkdtemp()) / "u.sqlite3"
        ReadingPlanRepository(BOOKS, path)
        self.assertEqual(sqlite3.connect(path).execute("PRAGMA journal_mode").fetchone()[0], "wal")


if __name__ == "__main__":
    unittest.main()
