"""Geracao de perguntas do quiz a partir do texto biblico."""
from __future__ import annotations

import random
from typing import Any

from app.bible.repository import BibleRepository


def build_questions(bible: BibleRepository, quantidade: int = 10) -> list[dict[str, Any]]:
    """Perguntas 'de qual livro e este versiculo?' geradas da Biblia."""
    book_names = [book["name"] for book in bible.books]
    perguntas: list[dict[str, Any]] = []
    tentativas = 0
    while len(perguntas) < quantidade and tentativas < quantidade * 40:
        tentativas += 1
        book = random.choice(bible.books)
        if not book["chapters"]:
            continue
        cap_index = random.randrange(len(book["chapters"]))
        chapter = book["chapters"][cap_index]
        if not chapter:
            continue
        verse_index = random.randrange(len(chapter))
        texto = str(chapter[verse_index]).strip()
        if not (55 <= len(texto) <= 240):
            continue

        distratores = [nome for nome in book_names if nome != book["name"]]
        opcoes = random.sample(distratores, 3) + [book["name"]]
        random.shuffle(opcoes)
        perguntas.append(
            {
                "texto": texto,
                "correta": book["name"],
                "referencia": f"{book['name']} {cap_index + 1}:{verse_index + 1}",
                "opcoes": opcoes,
            }
        )
    return perguntas
