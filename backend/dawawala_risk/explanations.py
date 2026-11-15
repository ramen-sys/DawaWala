"""Plain-language warning explanations (FR-13, SAF-06, QA-EXP-01/03/04).

Template based, no randomness. Each explanation states what was found, why it
matters, the rule ID and knowledge-base version, and sends the user to a
doctor or pharmacist. Free text that comes from the knowledge base
(``description``) is only included when it is safe to do so: it must fit the
word budget and must not tell the user to start, stop or change a medicine.
"""
from __future__ import annotations

import dataclasses
import re
from datetime import date
from typing import Iterable, List, Optional, Tuple

from . import templates as T
from .config import ScoringConfig
from .models import (
    DUPLICATE_THERAPEUTIC, FACTOR_LABELS, Category, ScoredWarning,
    WarningInput)

# SAF-06 / SAF-03: wording that must never appear in user-facing text.
_FORBIDDEN = re.compile(
    r"\b(?:"
    r"(?:stop|start|begin|quit|discontinue|cease|skip|avoid|"
    r"increase|decrease|reduce|lower|double|halve|adjust|change|switch|"
    r"swap|replace)\s+"
    r"(?:(?:to|your|the|this|that|these|those|its|their|a|an|any|all|each|"
    r"another|other)\s+){0,2}"
    r"(?:taking|using|it|them|dose|doses|dosage|medicine|medicines|"
    r"medication|medications|drug|drugs|tablet|tablets|pill|pills)"
    r"|do\s+not\s+(?:take|use)|don'?t\s+(?:take|use)"
    r"|you\s+(?:should|must|need\s+to)\s+(?:take|use|stop|start)"
    r"|safe(?:ly)?"
    r")\b",
    re.IGNORECASE)


def forbidden_phrases(text: str) -> List[str]:
    """Return any SAF-06 / SAF-03 violations found in ``text``."""
    return [m.group(0) for m in _FORBIDDEN.finditer(text)]


def word_count(text: str) -> int:
    return len(text.split())


def join_names(names: Iterable[str]) -> str:
    items = list(names)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _first_sentences(text: str, budget: int) -> str:
    """Longest run of whole sentences from ``text`` within ``budget`` words."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: List[str] = []
    used = 0
    for sentence in sentences:
        n = word_count(sentence)
        if used + n > budget:
            break
        kept.append(sentence)
        used += n
    return " ".join(kept)


def _core_sentences(sw: ScoredWarning) -> List[str]:
    w: WarningInput = sw.warning
    meds = join_names(w.medicines)
    sev = w.severity or ""
    if w.category is Category.INTERACTION:
        why = T.INTERACTION_SEVERITY.get(
            sev, T.INTERACTION_SEVERITY_DEFAULT.format(severity=sev))
        return [T.INTERACTION_FOUND.format(medicines=meds), why]
    if w.category is Category.CONTRAINDICATION:
        detail = (T.CONTRA_WITH_CONDITION.format(condition=w.condition)
                  if w.condition else T.CONTRA_NO_CONDITION)
        why = T.CONTRA_SEVERITY.get(
            sev, T.CONTRA_SEVERITY_DEFAULT.format(severity=sev))
        return [T.CONTRA_FOUND.format(medicines=meds), detail, why]
    if w.category is Category.DUPLICATE:
        text = (T.DUPLICATE_THERAPEUTIC
                if w.duplicate_kind == DUPLICATE_THERAPEUTIC
                else T.DUPLICATE_EXACT)
        return [text.format(medicines=meds)]
    # cascade
    if w.trigger and w.symptom_pattern and w.downstream:
        detail = T.CASCADE_DETAIL.format(
            trigger=w.trigger, symptom=w.symptom_pattern,
            downstream=w.downstream)
    else:
        detail = T.CASCADE_FALLBACK.format(medicines=meds)
    return [T.CASCADE_FOUND, detail, T.CASCADE_WHY]


def _tail_sentences(sw: ScoredWarning) -> List[str]:
    w = sw.warning
    tail: List[str] = []
    applied = [f for f in sw.factors if f.code.startswith("patient_")]
    if applied:
        names = [FACTOR_LABELS[f.code[len("patient_"):]] for f in applied]
        tail.append(T.FACTOR_LINE.format(factors=join_names(names)))
    tail.append(T.TRACE.format(rule_id=w.rule_id, kb_version=w.kb_version))
    tail.append(T.ADVICE)
    return tail


def build_explanation(
        sw: ScoredWarning,
        config: ScoringConfig) -> Tuple[str, Tuple[str, ...]]:
    """Return ``(text, notes)``; notes record any KB text that was left out."""
    core = " ".join(_core_sentences(sw))
    tail = " ".join(_tail_sentences(sw))
    notes: List[str] = []
    description = sw.warning.description.strip()
    middle = ""
    if description:
        budget = config.explanation_max_words - word_count(core + " " + tail)
        candidate = _first_sentences(description, budget)
        if not candidate:
            notes.append("description omitted: does not fit word limit")
        elif forbidden_phrases(candidate):
            notes.append("description omitted: contains forbidden wording")
        else:
            middle = candidate
            if candidate != description:
                notes.append("description shortened to fit word limit")
    text = " ".join(part for part in (core, middle, tail) if part)
    if word_count(text) > config.explanation_max_words:
        # Medicine names alone pushed the template over the limit.
        raise ValueError(
            f"explanation exceeds {config.explanation_max_words} words "
            f"for rule {sw.warning.rule_id}")
    leftover = forbidden_phrases(text)
    if leftover:
        raise ValueError(
            "explanation contains forbidden wording: " + ", ".join(leftover))
    return text, tuple(notes)


def explain(sw: ScoredWarning, config: ScoringConfig) -> ScoredWarning:
    """Return ``sw`` with its explanation (FR-13) filled in."""
    text, notes = build_explanation(sw, config)
    return dataclasses.replace(
        sw, explanation=text, explanation_notes=notes)


def kb_notice(
        kb_updated: date, today: Optional[date],
        config: ScoringConfig) -> Optional[str]:
    """SAF-07: notice when the knowledge base is older than KB_STALE_DAYS."""
    age = ((today or date.today()) - kb_updated).days
    if age > config.kb_stale_days:
        return ("The knowledge base was last updated more than "
                f"{config.kb_stale_days} days ago. Results may be out of "
                "date.")
    return None
