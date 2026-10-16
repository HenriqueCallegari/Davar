"""Backup/restauracao do UserDataManager (Turso simulado)."""
import gzip
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.bible.library import BibleLibrary
from app.config import Config
from app.core.user_data import UserDataManager, UserDataUnavailable

LIBRARY = BibleLibrary(Config.BIBLE_VERSIONS)


class FakeTurso:
    def __init__(self):
        self.blobs, self.fail, self.writes = {}, False, 0

    def execute(self, sql, args=None):
        if self.fail:
            raise RuntimeError("turso fora do ar")
        if sql.lstrip().startswith("SELECT data"):
            blob = self.blobs.get(args[0])
            return {"rows": [{"data": blob}] if blob else []}
        if sql.lstrip().startswith("INSERT"):
            self.blobs[args[0]] = args[1]
            self.writes += 1
        return {"rows": []}


def manager(turso, delay=0.2):
    users_dir = Path(tempfile.mkdtemp())
    return UserDataManager(LIBRARY.default, users_dir, turso=turso, backup_delay=delay), users_dir


class BackupTests(unittest.TestCase):
    def test_restore_failure_does_not_create_db_nor_overwrite_cloud(self):
        turso = FakeTurso()
        good = gzip.compress(b"backup-bom")
        turso.blobs[1] = good
        mgr, users_dir = manager(turso)
        turso.fail = True
        with self.assertRaises(UserDataUnavailable):
            mgr.get(1)
        self.assertFalse((users_dir / "user_1.sqlite3").exists())
        turso.fail = False
        self.assertFalse(mgr.backup(1))  # usuario nao aberto: nao envia nada
        self.assertEqual(turso.blobs[1], good)

    def test_debounce_coalesces_and_restore_roundtrip(self):
        turso = FakeTurso()
        mgr, _ = manager(turso)
        _, study = mgr.get(7)
        study.save_chapter_note("jo", 3, "minha reflexao")
        for _ in range(20):
            mgr.schedule_backup(7)
        time.sleep(0.8)
        self.assertEqual(turso.writes, 1)

        other, _ = manager(turso)  # "disco novo"
        self.assertEqual(other.study(7).get_chapter_note("jo", 3), "minha reflexao")

    def test_flush_sends_pending(self):
        turso = FakeTurso()
        mgr, _ = manager(turso, delay=60)
        mgr.study(3).save_chapter_note("jo", 1, "x")
        mgr.schedule_backup(3)
        mgr.flush()
        self.assertEqual(turso.writes, 1)

    def test_snapshot_is_consistent_under_concurrent_writes(self):
        turso = FakeTurso()
        mgr, _ = manager(turso)
        study = mgr.study(9)
        stop = threading.Event()

        def writer():
            i = 0
            while not stop.is_set():
                study.save_chapter_note("sl", 23, f"n{i}")
                i += 1

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            for _ in range(5):
                self.assertTrue(mgr.backup(9))
                path = Path(tempfile.mkdtemp()) / "x.sqlite3"
                path.write_bytes(gzip.decompress(turso.blobs[9]))
                self.assertEqual(sqlite3.connect(path).execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            stop.set()
            thread.join()


if __name__ == "__main__":
    unittest.main()
