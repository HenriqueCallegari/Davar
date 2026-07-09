"""Biblioteca de versoes biblicas.

Carrega multiplas traducoes e garante uma identidade canonica de livros
(abbrev/name/numero de capitulos) baseada na versao padrao. Assim, grifos,
progresso e URLs permanecem estaveis ao trocar de versao.

Cada versao e normalizada por POSICAO (indice do livro), o que torna o
sistema tolerante a arquivos com abreviacoes diferentes ou capitulos
excedentes (aparados contra o canon).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.bible.repository import BibleRepository, load_bible_json

logger = logging.getLogger(__name__)


class BibleLibrary:
    def __init__(self, versions: list[dict[str, Any]]) -> None:
        if not versions:
            raise ValueError("Nenhuma versao biblica configurada.")

        self._meta: list[dict[str, str]] = []
        self._repos: dict[str, BibleRepository] = {}
        self._default_id = next((v["id"] for v in versions if v.get("default")), versions[0]["id"])

        # A versao padrao define o canon (ordem, abreviacoes e nomes dos livros).
        default_cfg = next(v for v in versions if v["id"] == self._default_id)
        default_books = load_bible_json(default_cfg["path"])
        canon = [
            {"abbrev": book["abbrev"], "name": book["name"], "chapters": len(book["chapters"])}
            for book in default_books
        ]

        for cfg in versions:
            self._meta.append({"id": cfg["id"], "nome": cfg["nome"], "sigla": cfg["sigla"]})
            if cfg["id"] == self._default_id:
                self._repos[cfg["id"]] = BibleRepository(default_books)
                continue
            try:
                raw = load_bible_json(cfg["path"])
                self._repos[cfg["id"]] = BibleRepository(self._normalize(raw, canon, cfg["id"]))
            except FileNotFoundError:
                logger.warning("Versao '%s' ignorada: arquivo nao encontrado (%s)", cfg["id"], cfg["path"])

        # Mantem apenas versoes efetivamente carregadas na lista de metadados.
        self._meta = [m for m in self._meta if m["id"] in self._repos]

    def _normalize(self, raw: list[dict[str, Any]], canon: list[dict[str, Any]], version_id: str) -> list[dict[str, Any]]:
        """Alinha os livros ao canon por posicao e apara capitulos excedentes."""
        if len(raw) != len(canon):
            logger.warning("Versao '%s': %d livros (canon tem %d). Alinhando pelo menor.",
                           version_id, len(raw), len(canon))
        normalized: list[dict[str, Any]] = []
        for canonical, source in zip(canon, raw):
            chapters = source.get("chapters", [])
            if len(chapters) > canonical["chapters"]:
                logger.info("Versao '%s': aparando %s de %d para %d capitulos.",
                            version_id, canonical["abbrev"], len(chapters), canonical["chapters"])
                chapters = chapters[: canonical["chapters"]]
            normalized.append(
                {"abbrev": canonical["abbrev"], "name": canonical["name"], "chapters": chapters}
            )
        return normalized

    @property
    def default(self) -> BibleRepository:
        return self._repos[self._default_id]

    @property
    def default_id(self) -> str:
        return self._default_id

    @property
    def versions(self) -> list[dict[str, str]]:
        return self._meta

    def has(self, version_id: str) -> bool:
        return version_id in self._repos

    def version(self, version_id: str | None) -> BibleRepository:
        return self._repos.get(version_id or "", self.default)

    def version_meta(self, version_id: str) -> dict[str, str]:
        return next((m for m in self._meta if m["id"] == version_id), self._meta[0])
