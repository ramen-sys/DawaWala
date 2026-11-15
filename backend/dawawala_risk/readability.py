"""Flesch-Kincaid grade level (QA-EXP-03), standard library only."""
from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE_END = re.compile(r"[.!?]+(?:\s+|$)")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def count_syllables(word: str) -> int:
    """Heuristic English syllable count (at least 1)."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    count = len(_VOWEL_GROUP.findall(w))
    # silent trailing 'e' (but not 'le' as in "table")
    if w.endswith("e") and not w.endswith("le") and count > 1:
        count -= 1
    return max(count, 1)


def count_sentences(text: str) -> int:
    parts = [p for p in _SENTENCE_END.split(text.strip()) if p.strip()]
    return max(len(parts), 1)


def flesch_kincaid_grade(text: str) -> float:
    """FK grade = 0.39*(words/sentences) + 11.8*(syllables/words) - 15.59."""
    words = _WORD.findall(text)
    if not words:
        return 0.0
    syllables = sum(count_syllables(w) for w in words)
    sentences = count_sentences(text)
    return (0.39 * len(words) / sentences
            + 11.8 * syllables / len(words) - 15.59)
