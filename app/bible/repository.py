"""Acesso a Biblia: livros, capitulos, versiculos, busca e indice.

Carrega o JSON uma unica vez e mantem um indice plano em memoria para
buscas rapidas (palavra, frase, tema) sem depender de servico externo.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

OLD_TESTAMENT_BOOKS = 39  # primeiros 39 livros = Antigo Testamento


def normalize(text: str) -> str:
    """Minusculas e sem acento, para busca tolerante em portugues."""
    stripped = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return without_accents.lower()


def load_bible_json(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


@dataclass(frozen=True)
class VerseRef:
    abbrev: str
    book: str
    testament: str
    chapter: int
    verse: int
    text: str


class BibleRepository:
    """Fonte unica de verdade para o texto de UMA versao biblica."""

    def __init__(self, books: list[dict[str, Any]]) -> None:
        self._books = books
        self._by_abbrev = {book["abbrev"].lower(): book for book in self._books}
        self._index: list[VerseRef] = self._build_index()

    @classmethod
    def from_path(cls, path: Path) -> "BibleRepository":
        return cls(load_bible_json(path))

    # ---- catalogo -----------------------------------------------------
    @property
    def books(self) -> list[dict[str, Any]]:
        return self._books

    def book_summaries(self) -> list[dict[str, Any]]:
        return [
            {
                "abbrev": book["abbrev"],
                "name": book["name"],
                "chapters": len(book["chapters"]),
                "testament": self._testament(index),
            }
            for index, book in enumerate(self._books)
        ]

    def get_book(self, abbrev: str) -> dict[str, Any] | None:
        return self._by_abbrev.get(abbrev.lower())

    def chapter_count(self, abbrev: str) -> int:
        book = self.get_book(abbrev)
        return len(book["chapters"]) if book else 0

    def get_chapter(self, abbrev: str, number: int) -> list[str] | None:
        book = self.get_book(abbrev)
        if not book or not (1 <= number <= len(book["chapters"])):
            return None
        return book["chapters"][number - 1]

    def book_name(self, abbrev: str) -> str:
        book = self.get_book(abbrev)
        return book["name"] if book else abbrev

    def chapter_navigation(self, abbrev: str, number: int) -> dict[str, Any]:
        """Capitulo anterior/proximo, atravessando a fronteira dos livros."""
        book = self.get_book(abbrev)
        if not book:
            return {"prev": None, "next": None}
        book_index = next(
            (i for i, b in enumerate(self._books) if b["abbrev"].lower() == abbrev.lower()),
            None,
        )
        prev_ref = next_ref = None

        if number > 1:
            prev_ref = self._nav_entry(book["abbrev"], book["name"], number - 1)
        elif book_index:
            previous = self._books[book_index - 1]
            prev_ref = self._nav_entry(previous["abbrev"], previous["name"], len(previous["chapters"]))

        if number < len(book["chapters"]):
            next_ref = self._nav_entry(book["abbrev"], book["name"], number + 1)
        elif book_index is not None and book_index < len(self._books) - 1:
            following = self._books[book_index + 1]
            next_ref = self._nav_entry(following["abbrev"], following["name"], 1)

        return {"prev": prev_ref, "next": next_ref}

    @staticmethod
    def _nav_entry(abbrev: str, name: str, number: int) -> dict[str, Any]:
        return {"abbrev": abbrev, "name": name, "chapter": number, "label": f"{name} {number}"}

    # ---- indice / busca ----------------------------------------------
    def _testament(self, book_index: int) -> str:
        return "Antigo Testamento" if book_index < OLD_TESTAMENT_BOOKS else "Novo Testamento"

    def _build_index(self) -> list[VerseRef]:
        index: list[VerseRef] = []
        for book_index, book in enumerate(self._books):
            testament = self._testament(book_index)
            for chapter_index, verses in enumerate(book["chapters"], start=1):
                for verse_index, text in enumerate(verses, start=1):
                    index.append(
                        VerseRef(
                            abbrev=book["abbrev"],
                            book=book["name"],
                            testament=testament,
                            chapter=chapter_index,
                            verse=verse_index,
                            text=text,
                        )
                    )
        return index

    @property
    def total_verses(self) -> int:
        return len(self._index)

    @property
    def total_chapters(self) -> int:
        return sum(len(book["chapters"]) for book in self._books)

    def search(
        self,
        query: str,
        testament: str | None = None,
        abbrev: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Busca por palavra/frase, tolerante a acento e caixa."""
        needle = normalize(query).strip()
        results: list[dict[str, Any]] = []
        if not needle:
            return {"query": query, "total": 0, "results": results, "truncated": False}

        target_abbrev = abbrev.lower() if abbrev else None
        total = 0
        for ref in self._index:
            if testament and ref.testament != testament:
                continue
            if target_abbrev and ref.abbrev.lower() != target_abbrev:
                continue
            if needle in normalize(ref.text):
                total += 1
                if len(results) < limit:
                    results.append(
                        {
                            "abbrev": ref.abbrev,
                            "book": ref.book,
                            "testament": ref.testament,
                            "chapter": ref.chapter,
                            "verse": ref.verse,
                            "text": ref.text,
                        }
                    )
        return {
            "query": query,
            "total": total,
            "results": results,
            "truncated": total > len(results),
        }

    def collect_by_keywords(self, keywords: Iterable[str], limit: int = 60) -> list[dict[str, Any]]:
        """Reune versiculos que contenham qualquer palavra-chave (palavra inteira).

        Usa fronteira de palavra sobre o texto normalizado, evitando falsos
        positivos (ex.: 'fe' nao casa com 'fez' nem 'perfeito').
        """
        needles = [normalize(word) for word in keywords if word.strip()]
        if not needles:
            return []
        pattern = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in needles) + r")\b")
        found: list[dict[str, Any]] = []
        for ref in self._index:
            if pattern.search(normalize(ref.text)):
                found.append(
                    {
                        "abbrev": ref.abbrev,
                        "book": ref.book,
                        "reference": f"{ref.book} {ref.chapter}:{ref.verse}",
                        "chapter": ref.chapter,
                        "verse": ref.verse,
                        "text": ref.text,
                    }
                )
                if len(found) >= limit:
                    break
        return found

    def verse_of_the_day(self, seed: int) -> dict[str, Any]:
        """Versiculo deterministico do dia (mesmo para todos no mesmo dia)."""
        curated = self._curated_daily_pool()
        ref = curated[seed % len(curated)]
        return {
            "reference": f"{ref.book} {ref.chapter}:{ref.verse}",
            "abbrev": ref.abbrev,
            "chapter": ref.chapter,
            "verse": ref.verse,
            "text": ref.text,
        }

    def _curated_daily_pool(self) -> list[VerseRef]:
        """Selecao de versiculos consagrados para o versiculo do dia."""
        picks = [
            ("jo", 3, 16), ("sl", 23, 1), ("fp", 4, 13), ("pv", 3, 5),
            ("is", 41, 10), ("rm", 8, 28), ("js", 1, 9), ("mt", 6, 33),
            ("sl", 46, 1), ("fp", 4, 6), ("2tm", 1, 7), ("hb", 11, 1),
            ("pv", 3, 6), ("sl", 119, 105), ("gl", 5, 22), ("1co", 13, 4),
            ("ef", 2, 8), ("sl", 37, 4), ("jr", 29, 11), ("mt", 11, 28),
            ("rm", 12, 2), ("sl", 91, 1), ("is", 40, 31), ("cl", 3, 23),
        ]
        pool: list[VerseRef] = []
        for abbrev, chapter, verse in picks:
            text = self.verse_text(abbrev, chapter, verse)
            if text:
                pool.append(
                    VerseRef(
                        abbrev=abbrev,
                        book=self.book_name(abbrev),
                        testament="",
                        chapter=chapter,
                        verse=verse,
                        text=text,
                    )
                )
        return pool or self._index[:1]

    def verse_text(self, abbrev: str, chapter: int, verse: int) -> str | None:
        chapter_verses = self.get_chapter(abbrev, chapter)
        if chapter_verses and 1 <= verse <= len(chapter_verses):
            return chapter_verses[verse - 1]
        return None
