"""Camada de estudo: grifos por cor, anotacoes (markdown), favoritos e colecoes.

Persistencia em SQLite (mesmo arquivo dos planos, tabelas proprias).
Modelo de usuario unico por enquanto; estruturado para receber user_id no futuro.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.bible.repository import BibleRepository

VALID_COLORS = {"amarelo", "azul", "verde", "vermelho", "roxo"}

COLOR_MEANING = {
    "amarelo": "Promessa / esperanca",
    "azul": "Ensino / doutrina",
    "verde": "Crescimento / acao",
    "vermelho": "Alerta / correcao",
    "roxo": "Adoracao / oracao",
}


class StudyRepository:
    """Grifos, anotacoes, favoritos e colecoes do usuario."""

    def __init__(self, bible: BibleRepository, db_path: Path) -> None:
        self.bible = bible
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS highlights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abbrev TEXT NOT NULL,
                    capitulo INTEGER NOT NULL,
                    versiculo INTEGER NOT NULL,
                    cor TEXT NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (abbrev, capitulo, versiculo)
                );

                CREATE TABLE IF NOT EXISTS verse_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abbrev TEXT NOT NULL,
                    capitulo INTEGER NOT NULL,
                    versiculo INTEGER NOT NULL,
                    texto TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '',
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (abbrev, capitulo, versiculo)
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abbrev TEXT NOT NULL,
                    capitulo INTEGER NOT NULL,
                    versiculo INTEGER NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (abbrev, capitulo, versiculo)
                );

                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    descricao TEXT NOT NULL DEFAULT '',
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS collection_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL,
                    abbrev TEXT NOT NULL,
                    capitulo INTEGER NOT NULL,
                    versiculo INTEGER NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                    UNIQUE (collection_id, abbrev, capitulo, versiculo)
                );

                CREATE TABLE IF NOT EXISTS chapter_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abbrev TEXT NOT NULL,
                    capitulo INTEGER NOT NULL,
                    texto TEXT NOT NULL DEFAULT '',
                    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (abbrev, capitulo)
                );
                """
            )

    # ---- grifos -------------------------------------------------------
    def set_highlight(self, abbrev: str, chapter: int, verse: int, color: str | None) -> dict[str, Any]:
        """Define, troca ou remove (color=None) o grifo de um versiculo."""
        with self._connect() as connection:
            if color is None:
                connection.execute(
                    "DELETE FROM highlights WHERE abbrev = ? AND capitulo = ? AND versiculo = ?",
                    (abbrev, chapter, verse),
                )
                return {"abbrev": abbrev, "capitulo": chapter, "versiculo": verse, "cor": None}
            if color not in VALID_COLORS:
                raise ValueError(f"Cor invalida: {color}")
            connection.execute(
                """
                INSERT INTO highlights (abbrev, capitulo, versiculo, cor)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(abbrev, capitulo, versiculo) DO UPDATE SET cor = excluded.cor
                """,
                (abbrev, chapter, verse, color),
            )
            return {"abbrev": abbrev, "capitulo": chapter, "versiculo": verse, "cor": color}

    def set_highlights_batch(
        self, abbrev: str, chapter: int, verses: list[int], color: str | None
    ) -> dict[str, Any]:
        """Aplica (ou remove) a mesma cor a varios versiculos de uma vez."""
        if color is not None and color not in VALID_COLORS:
            raise ValueError(f"Cor invalida: {color}")
        with self._connect() as connection:
            if color is None:
                connection.executemany(
                    "DELETE FROM highlights WHERE abbrev = ? AND capitulo = ? AND versiculo = ?",
                    [(abbrev, chapter, verse) for verse in verses],
                )
            else:
                connection.executemany(
                    """
                    INSERT INTO highlights (abbrev, capitulo, versiculo, cor)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(abbrev, capitulo, versiculo) DO UPDATE SET cor = excluded.cor
                    """,
                    [(abbrev, chapter, verse, color) for verse in verses],
                )
        return {"abbrev": abbrev, "capitulo": chapter, "versiculos": verses, "cor": color}

    # ---- favoritos ----------------------------------------------------
    def toggle_favorite(self, abbrev: str, chapter: int, verse: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM favorites WHERE abbrev = ? AND capitulo = ? AND versiculo = ?",
                (abbrev, chapter, verse),
            ).fetchone()
            if row:
                connection.execute("DELETE FROM favorites WHERE id = ?", (row["id"],))
                return {"favorito": False}
            connection.execute(
                "INSERT INTO favorites (abbrev, capitulo, versiculo) VALUES (?, ?, ?)",
                (abbrev, chapter, verse),
            )
            return {"favorito": True}

    # ---- anotacoes ----------------------------------------------------
    def save_note(self, abbrev: str, chapter: int, verse: int, texto: str, tags: str = "") -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        clean_tags = ",".join(
            tag.strip() for tag in tags.replace("#", "").split(",") if tag.strip()
        )
        with self._connect() as connection:
            if not texto.strip():
                connection.execute(
                    "DELETE FROM verse_notes WHERE abbrev = ? AND capitulo = ? AND versiculo = ?",
                    (abbrev, chapter, verse),
                )
                return {"removido": True}
            connection.execute(
                """
                INSERT INTO verse_notes (abbrev, capitulo, versiculo, texto, tags, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(abbrev, capitulo, versiculo) DO UPDATE SET
                    texto = excluded.texto,
                    tags = excluded.tags,
                    atualizado_em = excluded.atualizado_em
                """,
                (abbrev, chapter, verse, texto, clean_tags, now, now),
            )
            return {"salvo": True, "tags": clean_tags.split(",") if clean_tags else [], "atualizado_em": now}

    # ---- leitura: marcas do capitulo ---------------------------------
    def chapter_marks(self, abbrev: str, chapter: int) -> dict[str, Any]:
        """Grifos, favoritos e notas de um capitulo, prontos para o front."""
        with self._connect() as connection:
            highlights = {
                row["versiculo"]: row["cor"]
                for row in connection.execute(
                    "SELECT versiculo, cor FROM highlights WHERE abbrev = ? AND capitulo = ?",
                    (abbrev, chapter),
                ).fetchall()
            }
            favorites = [
                row["versiculo"]
                for row in connection.execute(
                    "SELECT versiculo FROM favorites WHERE abbrev = ? AND capitulo = ?",
                    (abbrev, chapter),
                ).fetchall()
            ]
            notes = {
                row["versiculo"]: {"texto": row["texto"], "tags": row["tags"]}
                for row in connection.execute(
                    "SELECT versiculo, texto, tags FROM verse_notes WHERE abbrev = ? AND capitulo = ?",
                    (abbrev, chapter),
                ).fetchall()
            }
        return {"highlights": highlights, "favorites": favorites, "notes": notes}

    # ---- reflexao do capitulo ("O que Deus falou comigo") ------------
    def get_chapter_note(self, abbrev: str, chapter: int) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT texto FROM chapter_notes WHERE abbrev = ? AND capitulo = ?",
                (abbrev, chapter),
            ).fetchone()
        return row["texto"] if row else ""

    def save_chapter_note(self, abbrev: str, chapter: int, texto: str) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            if not texto.strip():
                connection.execute(
                    "DELETE FROM chapter_notes WHERE abbrev = ? AND capitulo = ?",
                    (abbrev, chapter),
                )
                return {"salvo": True, "removido": True}
            connection.execute(
                """
                INSERT INTO chapter_notes (abbrev, capitulo, texto, atualizado_em)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(abbrev, capitulo) DO UPDATE SET texto = excluded.texto, atualizado_em = excluded.atualizado_em
                """,
                (abbrev, chapter, texto, now),
            )
        return {"salvo": True, "atualizado_em": now}

    def list_chapter_notes(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT abbrev, capitulo, texto, atualizado_em FROM chapter_notes ORDER BY atualizado_em DESC"
            ).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["reference"] = "%s %d" % (self.bible.book_name(row["abbrev"]), row["capitulo"])
            result.append(data)
        return result

    # ---- painel de estudo --------------------------------------------
    def list_highlights(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT abbrev, capitulo, versiculo, cor, criado_em FROM highlights ORDER BY criado_em DESC"
            ).fetchall()
        return [self._decorate(dict(row)) for row in rows]

    def list_favorites(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT abbrev, capitulo, versiculo, criado_em FROM favorites ORDER BY criado_em DESC"
            ).fetchall()
        return [self._decorate(dict(row)) for row in rows]

    def list_notes(self, query: str = "") -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT abbrev, capitulo, versiculo, texto, tags, atualizado_em FROM verse_notes ORDER BY atualizado_em DESC"
            ).fetchall()
        notes = [self._decorate(dict(row)) for row in rows]
        if query:
            needle = query.lower()
            notes = [
                note
                for note in notes
                if needle in note["texto"].lower() or needle in note["tags"].lower()
            ]
        for note in notes:
            note["tag_list"] = [t for t in note["tags"].split(",") if t]
        return notes

    def export_all(self) -> dict[str, Any]:
        return {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "highlights": self.list_highlights(),
            "favorites": self.list_favorites(),
            "notes": self.list_notes(),
            "collections": [self.get_collection(c["id"]) for c in self.list_collections()],
        }

    # ---- colecoes -----------------------------------------------------
    def list_collections(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.nome, c.descricao,
                       COUNT(ci.id) AS total
                FROM collections c
                LEFT JOIN collection_items ci ON ci.collection_id = c.id
                GROUP BY c.id
                ORDER BY c.nome
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_collection(self, nome: str, descricao: str = "") -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO collections (nome, descricao) VALUES (?, ?)",
                (nome.strip() or "Nova colecao", descricao.strip()),
            )
            return {"id": cursor.lastrowid, "nome": nome, "descricao": descricao}

    def delete_collection(self, collection_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM collections WHERE id = ?", (collection_id,))

    def add_to_collection(self, collection_id: int, abbrev: str, chapter: int, verse: int) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO collection_items (collection_id, abbrev, capitulo, versiculo)
                VALUES (?, ?, ?, ?)
                """,
                (collection_id, abbrev, chapter, verse),
            )
        return {"ok": True}

    def remove_from_collection(self, collection_id: int, abbrev: str, chapter: int, verse: int) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM collection_items WHERE collection_id = ? AND abbrev = ? AND capitulo = ? AND versiculo = ?",
                (collection_id, abbrev, chapter, verse),
            )
        return {"ok": True}

    def get_collection(self, collection_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            collection = connection.execute(
                "SELECT id, nome, descricao FROM collections WHERE id = ?",
                (collection_id,),
            ).fetchone()
            if collection is None:
                return None
            rows = connection.execute(
                "SELECT abbrev, capitulo, versiculo, criado_em FROM collection_items WHERE collection_id = ? ORDER BY criado_em DESC",
                (collection_id,),
            ).fetchall()
        data = dict(collection)
        data["items"] = [self._decorate(dict(row)) for row in rows]
        return data

    # ---- helpers ------------------------------------------------------
    def _decorate(self, row: dict[str, Any]) -> dict[str, Any]:
        """Anexa nome do livro, referencia e texto do versiculo."""
        abbrev = row["abbrev"]
        chapter = row["capitulo"]
        verse = row["versiculo"]
        book = self.bible.book_name(abbrev)
        row["book"] = book
        row["reference"] = f"{book} {chapter}:{verse}"
        row["text"] = self.bible.verse_text(abbrev, chapter, verse) or ""
        return row
