"""Geradores dos jogos e exercicios, sempre a partir do TEXTO da Biblia
(nada de conteudo biblico inventado).

Cada gerador recebe o repositorio da versao ativa e um `random.Random`, o que
permite o "desafio do dia" (mesma semente para todos) e testes reproduziveis.
"""
from __future__ import annotations

import random
import re
from typing import Any

from app.bible.repository import BibleRepository, VerseRef, normalize

BLANK_MIN_LEN = 5  # so vira lacuna palavra com pelo menos 5 letras
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")

# Palavras comuns demais para serem boas lacunas (comparadas sem acento/caixa).
STOPWORDS = frozenset(normalize(w) for w in (
    "antes", "assim", "alguns", "algumas", "ainda", "aquele", "aquela", "aqueles", "aquelas",
    "ambos", "apenas", "cada", "contra", "depois", "desde", "disse", "dizer", "entre", "esses",
    "essas", "este", "estes", "estas", "havia", "mesmo", "mesma", "muito", "muitos", "nossa",
    "nosso", "nossos", "nossas", "outra", "outro", "outros", "outras", "pelas", "pelos", "porque",
    "quando", "quais", "qualquer", "quem", "sobre", "senhor", "sejam", "seria", "tanto", "tinha",
    "todos", "todas", "toda", "todo", "vossa", "vosso", "vossos", "vossas", "porém", "então",
    "também", "assim", "onde", "além", "agora", "nunca", "sempre", "ainda", "aqui", "disso",
    "dele", "dela", "deles", "delas", "isto", "isso", "aquilo", "esse", "essa", "esta", "estava",
    "foram", "fosse", "seus", "suas", "seu", "sua", "teus", "tuas", "vindo", "ficou", "fazer",
))

TESTAMENTS = ("Antigo Testamento", "Novo Testamento")


def _ref_fields(ref: VerseRef) -> dict[str, Any]:
    return {
        "referencia": f"{ref.book} {ref.chapter}:{ref.verse}",
        "abbrev": ref.abbrev,
        "capitulo": ref.chapter,
        "versiculo": ref.verse,
    }


def _blank_candidates(text: str) -> list[re.Match[str]]:
    return [m for m in WORD_RE.finditer(text)
            if len(m.group()) >= BLANK_MIN_LEN and normalize(m.group()) not in STOPWORDS]


def _match_case(word: str, like: str) -> str:
    """Capitaliza `word` se `like` for capitalizada (e vice-versa), para a lacuna nao denunciar a resposta."""
    if like[:1].isupper():
        return word[:1].upper() + word[1:]
    return word[:1].lower() + word[1:]


def cloze_questions(bible: BibleRepository, rng: random.Random, count: int,
                    abbrev: str | None = None, chapter: int | None = None) -> list[dict[str, Any]]:
    """"Complete o versiculo": uma palavra some e o jogador escolhe a certa."""
    verses = bible.pick_verses(rng, count * 3, 50, 200, abbrev, chapter)
    # Vocabulario para distratores: palavras de outros versiculos da propria Biblia.
    vocab_refs = bible.pick_verses(rng, 40, 50, 200)
    vocabulary = {}
    for ref in vocab_refs:
        for m in _blank_candidates(ref.text):
            vocabulary.setdefault(normalize(m.group()), m.group())

    questions: list[dict[str, Any]] = []
    for ref in verses:
        candidates = _blank_candidates(ref.text)
        if not candidates:
            continue
        target = rng.choice(candidates)
        correct = target.group()
        key = normalize(correct)
        similar = [w for k, w in vocabulary.items()
                   if k != key and abs(len(w) - len(correct)) <= 2]
        others = [w for k, w in vocabulary.items() if k != key and w not in similar]
        rng.shuffle(similar)
        rng.shuffle(others)
        distractors = [_match_case(w, correct) for w in (similar + others)[:3]]
        if len(distractors) < 3:
            continue
        options = distractors + [correct]
        rng.shuffle(options)
        questions.append({
            "antes": ref.text[:target.start()],
            "depois": ref.text[target.end():],
            "correta": correct,
            "opcoes": options,
            **_ref_fields(ref),
        })
        if len(questions) >= count:
            break
    return questions


def scramble_questions(bible: BibleRepository, rng: random.Random, count: int,
                       abbrev: str | None = None, chapter: int | None = None) -> list[dict[str, Any]]:
    """"Monte o versiculo": versiculos curtos para reordenar palavra por palavra."""
    verses = bible.pick_verses(rng, count * 4, 25, 130, abbrev, chapter)
    questions = []
    for ref in verses:
        words = ref.text.split()
        if not 4 <= len(words) <= 14:
            continue
        questions.append({"palavras": words, "texto": ref.text, **_ref_fields(ref)})
        if len(questions) >= count:
            break
    return questions


def testament_questions(bible: BibleRepository, rng: random.Random, count: int) -> list[dict[str, Any]]:
    """"Relampago": este versiculo e do Antigo ou do Novo Testamento?"""
    half = count // 2 + 1
    verses: list[VerseRef] = []
    for testament in TESTAMENTS:  # equilibra os dois lados
        verses += bible.pick_verses(rng, half, 60, 200, testament=testament)
    rng.shuffle(verses)
    return [{"texto": ref.text, "correta": ref.testament, **_ref_fields(ref)} for ref in verses[:count]]


def match_pairs(bible: BibleRepository, rng: random.Random, pairs: int = 6) -> list[dict[str, Any]]:
    """"Pares": combine o trecho com a sua referencia (livros diferentes, sem ambiguidade)."""
    verses = bible.pick_verses(rng, pairs * 4, 30, 95)
    chosen, books = [], set()
    for ref in verses:
        if ref.abbrev in books:
            continue
        books.add(ref.abbrev)
        chosen.append({"id": len(chosen), "texto": ref.text, **_ref_fields(ref)})
        if len(chosen) >= pairs:
            break
    return chosen
