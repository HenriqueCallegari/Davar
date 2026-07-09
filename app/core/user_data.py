"""Gerencia os repositorios de dados por usuario.

Cada conta tem seu proprio arquivo SQLite (instance/users/user_<id>.sqlite3),
o que garante isolamento total: um usuario nunca ve os dados de outro.
Os repositorios sao cacheados por usuario para evitar re-seed a cada request.
"""
from __future__ import annotations

from pathlib import Path

from app.bible.repository import BibleRepository
from app.plans.repository import ReadingPlanRepository
from app.study.repository import StudyRepository


class UserDataManager:
    def __init__(self, bible: BibleRepository, users_dir: Path) -> None:
        self.bible = bible
        self.users_dir = Path(users_dir)
        self._cache: dict[int, tuple[ReadingPlanRepository, StudyRepository]] = {}

    def _db_path(self, user_id: int) -> Path:
        return self.users_dir / f"user_{user_id}.sqlite3"

    def get(self, user_id: int) -> tuple[ReadingPlanRepository, StudyRepository]:
        if user_id not in self._cache:
            db_path = self._db_path(user_id)
            plans = ReadingPlanRepository(self.bible.books, db_path)
            study = StudyRepository(self.bible, db_path)
            self._cache[user_id] = (plans, study)
        return self._cache[user_id]

    def plans(self, user_id: int) -> ReadingPlanRepository:
        return self.get(user_id)[0]

    def study(self, user_id: int) -> StudyRepository:
        return self.get(user_id)[1]
