"""Estudo do capitulo: sintese teologica original, escrita a mao e servida
a partir de arquivos estaticos (nao gerada por IA em tempo real).

Cada arquivo em data/estudos/<abbrev>.json contem os estudos de um livro,
indexados por numero de capitulo (string). O conteudo (resumo, contexto,
mensagens-chave e perguntas de reflexao) e o mesmo para qualquer versao da
Biblia (KJA, NTLH etc.), pois trata do significado teologico do capitulo,
nao do texto de uma traducao especifica.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ChapterStudyService:
    def __init__(self, studies_dir: Path) -> None:
        self.studies_dir = Path(studies_dir)
        self._index: dict[str, dict[str, dict[str, Any]]] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.studies_dir.exists():
            return
        for path in sorted(self.studies_dir.glob("*.json")):
            abbrev = path.stem
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    self._index[abbrev] = json.load(handle)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Falha ao carregar estudos de %s: %s", path, exc)

    @property
    def total_chapters_available(self) -> int:
        return sum(len(chapters) for chapters in self._index.values())

    def get(self, abbrev: str, chapter: int) -> dict[str, Any] | None:
        book = self._index.get(abbrev.lower())
        if book is None:
            return None
        return book.get(str(chapter))

    def generate(
        self, version_id: str, abbrev: str, chapter: int, book_name: str, verses: list[str]
    ) -> dict[str, Any]:
        """Mantem a mesma assinatura/contrato da versao anterior (baseada em IA),
        para nao precisar alterar a rota. version_id/book_name/verses sao
        ignorados: o conteudo e o mesmo para qualquer versao biblica."""
        content = self.get(abbrev, chapter)
        if content is None:
            return {
                "disponivel": False,
                "motivo": "O estudo deste capítulo ainda não foi escrito. Estamos preparando aos poucos.",
            }
        return {"disponivel": True, **content}
