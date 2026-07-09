"""Indice tematico: reune automaticamente versiculos por tema.

Le uma lista curada de temas (slug + palavras-chave) e usa o indice da
Biblia para juntar os versiculos, com cache em memoria por tema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.bible.repository import BibleRepository


class ThemeService:
    def __init__(self, bible: BibleRepository, themes_path: Path, per_theme_limit: int = 60) -> None:
        self.bible = bible
        self.per_theme_limit = per_theme_limit
        with open(themes_path, "r", encoding="utf-8") as handle:
            self._themes: list[dict[str, Any]] = json.load(handle)
        self._by_slug = {theme["slug"]: theme for theme in self._themes}
        self._verse_cache: dict[str, list[dict[str, Any]]] = {}

    def list_themes(self) -> list[dict[str, Any]]:
        return [
            {
                "slug": theme["slug"],
                "nome": theme["nome"],
                "icone": theme["icone"],
                "descricao": theme["descricao"],
            }
            for theme in self._themes
        ]

    def get_theme(self, slug: str) -> dict[str, Any] | None:
        theme = self._by_slug.get(slug)
        if theme is None:
            return None
        if slug not in self._verse_cache:
            self._verse_cache[slug] = self.bible.collect_by_keywords(
                theme["palavras"], limit=self.per_theme_limit
            )
        return {
            "slug": theme["slug"],
            "nome": theme["nome"],
            "icone": theme["icone"],
            "descricao": theme["descricao"],
            "verses": self._verse_cache[slug],
        }
