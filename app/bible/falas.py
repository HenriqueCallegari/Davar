"""Falas de Jesus ("letras vermelhas").

O texto das traducoes nao marca quem esta falando, entao as falas ficam num
mapa a parte (`data/falas_jesus.json`) que vale para QUALQUER versao, pois e
indexado pelo canone (livro/capitulo/versiculo). Formato por capitulo — uma lista
de fichas:
  "N"      versiculo N inteiro        "N-M"    versiculos N a M inteiros
  "Nc"     a fala comeca depois do 1o ":" do versiculo N (narracao antes) e vai ate o fim
  "Nc2"    a fala comeca depois do 2o ":" do versiculo N
  "Ns"     a fala vai do inicio do versiculo ate o fim da 1a frase (narracao depois);
           "Ns2" = ate o fim da 2a frase
  "Ncs"    narracao, ":" e uma frase de fala, depois narracao (ex.: "Jesus disse: Maria!"
           ou "...disse: Esta consumado. E, inclinando a cabeca, expirou");
           "Nc2s2" = depois do 2o ":", duas frases
Como os pontos de corte sao o ":" e a pontuacao do proprio texto, o mesmo mapa serve
para KJA e NTLH.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from markupsafe import Markup, escape

logger = logging.getLogger(__name__)

_RANGE = re.compile(r"^(\d+)(?:-(\d+))?$")
_PARTIAL = re.compile(r"^(\d+)(?:c(\d?))?(?:s(\d?))?$")  # N + (c[n]) e/ou (s[k])
_SENTENCE_END = ".!?"
_CLOSERS = "”»\"')"  # aspas/parenteses que podem fechar a frase depois do ponto
_DASHES = "\u2014\u2013"
_VERBS = (
    "disse|respondeu|perguntou|afirmou|ordenou|declarou|falou|exclamou|replicou|continuou|"
    "acrescentou|insistiu|completou|prosseguiu|observou|explicou"
)
_VERBS_ANY = _VERBS + "|responderam|perguntaram|disseram|gritou|gritaram|retrucou|retrucaram|sussurrou|chamou"
# NTLH escreve dialogos como "\u2014 Venham ver! \u2014 disse Jesus." (fala primeiro, etiqueta depois).
_TAGGED_SPEECH = re.compile(
    rf"^\s*[\u2014\u2013-]\s*(?P<fala>[^\u2014\u2013]+?)\s*[\u2014\u2013]\s*(?:{_VERBS})\s+Jesus\b"
)
_ANY_TAG = re.compile(rf"[\u2014\u2013]\s*(?:{_VERBS_ANY})\b")
_SKIP_AFTER_COLON = "  —–-"  # espaco, nbsp e travessoes que a NTLH usa ("disse: — Eu...")
_INTRO_JESUS = re.compile(r"Jesus|\bvoz\b")  # quem fala logo antes do ':'  (Jesus ou "a voz" do alto)


class FalasJesus:
    def __init__(self, path: Path | None = None, mapping: dict[str, dict[str, list[str]]] | None = None) -> None:
        if mapping is None:
            mapping = {}
            if path is not None and Path(path).exists():
                with open(path, "r", encoding="utf-8") as handle:
                    mapping = json.load(handle)
            else:
                logger.warning("Mapa de falas de Jesus nao encontrado (%s).", path)
        # (abbrev, capitulo) -> {versiculo: (colon, sentences)}; (0, 0) = versiculo inteiro
        self._verses: dict[tuple[str, int], dict[int, tuple[int, int]]] = {}
        for abbrev, chapters in mapping.items():
            for chapter, tokens in chapters.items():
                marks: dict[int, tuple[int, int]] = {}
                for token in tokens:
                    self._parse(token, marks)
                self._verses[(abbrev.lower(), int(chapter))] = marks

    @staticmethod
    def _parse(token: str, marks: dict[int, tuple[int, int]]) -> None:
        match = _RANGE.match(token)
        if match:
            first = int(match.group(1))
            last = int(match.group(2) or first)
            for verse in range(first, last + 1):
                marks[verse] = (0, 0)
            return
        match = _PARTIAL.match(token)
        if match and ("c" in token or "s" in token):
            colon = int(match.group(2) or 1) if "c" in token else 0
            sentences = int(match.group(3) or 1) if "s" in token else 0
            marks[int(match.group(1))] = (colon, sentences)
            return
        raise ValueError(f"Ficha invalida no mapa de falas: {token!r}")

    @property
    def total_verses(self) -> int:
        return sum(len(marks) for marks in self._verses.values())

    def mode(self, abbrev: str, chapter: int, verse: int) -> tuple[int, int] | None:
        marks = self._verses.get((abbrev.lower(), chapter))
        return None if marks is None else marks.get(verse)

    def parts(self, abbrev: str, chapter: int, verse: int, text: str) -> list[tuple[str, bool]]:
        """Divide o versiculo em trechos (texto, e_fala_de_jesus)."""
        mode = self.mode(abbrev, chapter, verse)
        if mode is None:
            return [(text, False)]
        colon, sentences = mode
        if colon == 0 and sentences == 0:
            return [(text, True)]

        start = 0
        if colon:  # a fala comeca depois do n-esimo ':'
            position = -1
            for _ in range(colon):
                position = text.find(":", position + 1)
                if position == -1:
                    return self._dialogue_fallback(text, sentences)
            start = position + 1
            while start < len(text) and text[start] in _SKIP_AFTER_COLON:
                start += 1
            if start >= len(text):
                return [(text, False)]

        end = len(text)
        if sentences:  # a fala termina no fim da k-esima frase
            end = self._sentence_end(text, start, sentences)

        pieces = [(text[:start], False), (text[start:end], True), (text[end:], False)]
        return [(chunk, red) for chunk, red in pieces if chunk]

    @staticmethod
    def _cut(text: str, spans: list[tuple[int, int]]) -> list[tuple[str, bool]]:
        """Divide `text` em trechos, vermelhos nos intervalos `spans` (ordenados, sem sobreposicao)."""
        out, pos = [], 0
        for start, end in spans:
            if start > pos:
                out.append((text[pos:start], False))
            if end > start:
                out.append((text[start:end], True))
            pos = max(pos, end)
        if pos < len(text):
            out.append((text[pos:], False))
        return out

    def _dialogue_fallback(self, text: str, sentences: int) -> list[tuple[str, bool]]:
        """Versoes cujo texto nao traz o ':' esperado (ex.: dialogos com travessao da NTLH).
        So colore quando o formato e inequivoco; do contrario deixa sem cor."""
        plain = [(text, False)]
        # 1) "\u2014 fala \u2014 disse Jesus." (+ a continuacao da fala depois da etiqueta)
        match = _TAGGED_SPEECH.match(text)
        if match:
            spans = [match.span("fala")]
            rest = text[match.end():]
            lead = len(rest) - len(rest.lstrip(".!?,;: \u00a0"))
            if rest[lead:lead + 1] in tuple(_DASHES):
                cont = match.end() + lead + 1
                while cont < len(text) and text[cont] in " \u00a0":
                    cont += 1
                other = _ANY_TAG.search(text, cont)
                spans.append((cont, other.start() if other else len(text)))
            return self._cut(text, spans)
        # 2) menos ':' que o esperado: usa o ultimo, se quem fala antes dele for Jesus
        last = text.rfind(":")
        if last != -1:
            if not _INTRO_JESUS.search(text[max(0, last - 40):last]):
                return plain
            start = last + 1
            while start < len(text) and text[start] in _SKIP_AFTER_COLON:
                start += 1
            if start >= len(text):
                return plain
            end = self._sentence_end(text, start, sentences) if sentences else len(text)
            return self._cut(text, [(start, end)])
        # 3) versiculo que ja comeca na fala (a introducao ficou no anterior), sem etiqueta de outro falante
        stripped = text.lstrip()
        if stripped[:1] in _DASHES and not _ANY_TAG.search(text):
            start = len(text) - len(stripped) + 1
            while start < len(text) and text[start] in " \u00a0":
                start += 1
            end = self._sentence_end(text, start, sentences) if sentences else len(text)
            if start < end:
                return self._cut(text, [(start, end)])
        return plain

    @staticmethod
    def _sentence_end(text: str, start: int, count: int) -> int:
        """Indice logo apos a pontuacao final da `count`-esima frase a partir de `start`."""
        seen = 0
        i = start
        while i < len(text):
            if text[i] in _SENTENCE_END:
                j = i + 1
                while j < len(text) and text[j] in _SENTENCE_END + _CLOSERS:
                    j += 1
                if j >= len(text) or text[j] in " \u00a0":
                    seen += 1
                    if seen == count:
                        return j
                i = j
            else:
                i += 1
        return len(text)

    def render(self, text: str, abbrev: str, chapter: int, verse: int) -> Markup:
        """HTML seguro do versiculo com as falas de Jesus em <span class="fala-jesus">."""
        pieces = []
        for chunk, red in self.parts(abbrev, chapter, verse, text):
            safe = escape(chunk)
            pieces.append(f'<span class="fala-jesus">{safe}</span>' if red else str(safe))
        return Markup("".join(pieces))

    def as_json(self, abbrev: str, chapter: int, verse: int, text: str) -> list[list[Any]]:
        """Mesmo que parts(), em formato serializavel (para as APIs)."""
        return [[chunk, red] for chunk, red in self.parts(abbrev, chapter, verse, text)]
