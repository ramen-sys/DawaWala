"""Extract medicine terms and match them against standard names and aliases."""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Medication, MedicationAlias
from app.models.enums import ConfidenceLabel

MIN_CANDIDATE_SCORE = 70
MAX_TERM_WORDS = 6
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|%)", re.IGNORECASE)
_NON_DRUG_TEXT = re.compile(
    r"\b(?:"
    r"\d+(?:\.\d+)?\s*(?:mg|mcg|g|kg|ml|l|iu|units?|%|mmol)?"
    r"|(?:\d+\s*-\s*){1,3}\d+"
    r"|take|takes|taking|use|uses|using|apply|applies|applied|"
    r"tablet|tablets|tab|tabs|capsule|capsules|cap|caps|syrup|suspension|"
    r"injection|injectable|cream|ointment|drop|drops|oral|"
    r"once|twice|thrice|daily|weekly|every|each|morning|noon|evening|night|bedtime|"
    r"before|after|with|without|food|meal|meals|"
    r"day|days|week|weeks|month|months|hour|hours|"
    r"as\s+needed|if\s+needed|prn|od|bd|tds|qid|hs|"
    r"for|then|and|or|one|two|three|four|five|six"
    r")\b",
    re.IGNORECASE,
)

VocabularyEntry = tuple[int, str, str]


@dataclass
class NormalizationResult:
    medication_id: int | None = None
    match_score: int | None = None


def medication_vocabulary(db: Session) -> list[VocabularyEntry]:
    """Load standard names and aliases for term extraction and fuzzy matching."""
    standard_names = select(
        Medication.id,
        Medication.standard_name,
        Medication.standard_name.label("match_name"),
    )
    aliases = (
        select(Medication.id, Medication.standard_name, MedicationAlias.alias.label("match_name"))
        .join(MedicationAlias, MedicationAlias.medication_id == Medication.id)
    )
    return list(db.execute(standard_names.union_all(aliases)).all())


def extract_drug_term(raw_text: str) -> str:
    """Remove strengths, forms, and common instructions from one manually entered name."""
    without_notes = _NON_DRUG_TEXT.sub(" ", raw_text)
    return " ".join(without_notes.split()).strip(" -,.;:")


def extract_strengths(raw_text: str) -> list[str]:
    return [f"{number}{unit.lower()}" for number, unit in _STRENGTH.findall(raw_text)]


def _normalized_words(text: str) -> tuple[str, ...]:
    return tuple(word.casefold() for word in _WORD.findall(text))


def confidence_label(match_score: int | None) -> ConfidenceLabel:
    """Apply FR-6 confidence bands; no score means no candidate was recognized."""
    if match_score is None or match_score < settings.MATCH_LOW:
        return ConfidenceLabel.UNRECOGNISED
    if match_score >= settings.MATCH_HIGH:
        return ConfidenceLabel.HIGH
    return ConfidenceLabel.LOW


def _rank_candidates(term: str, vocabulary: list[VocabularyEntry], limit: int = 3) -> list[dict]:
    normalized_term = " ".join(_normalized_words(term))
    if not normalized_term:
        return []

    best: dict[int, dict] = {}
    for medication_id, standard_name, match_name in vocabulary:
        score = round(fuzz.ratio(normalized_term, " ".join(_normalized_words(match_name))))
        if score < MIN_CANDIDATE_SCORE:
            continue
        current = best.get(medication_id)
        if current is None or score > current["match_score"]:
            best[medication_id] = {
                "medication_id": medication_id,
                "standard_name": standard_name,
                "matched_alias": match_name,
                "match_score": score,
                "label": confidence_label(score).value,
            }

    return sorted(best.values(), key=lambda candidate: (-candidate["match_score"], candidate["medication_id"]))[:limit]


def extract_medication_terms(raw_text: str, vocabulary: list[VocabularyEntry]) -> list[dict]:
    """Extract recognizable medicine-name spans from OCR text, ignoring surrounding directions.

    Only spans matching a standard name or alias at FR-6's 70-point minimum become
    medication items. The original full OCR transcription remains separate for review.
    """
    matchable_text = _NON_DRUG_TEXT.sub(lambda match: " " * len(match.group()), raw_text)
    words = _WORD.findall(matchable_text)
    if not words or not vocabulary:
        return []

    max_words = min(MAX_TERM_WORDS, max(len(_normalized_words(entry[2])) for entry in vocabulary))
    word_spans = list(_WORD.finditer(matchable_text))
    found: list[dict] = []
    start = 0
    while start < len(words):
        best_match: tuple[int, int, str, list[dict]] | None = None
        for size in range(min(max_words, len(words) - start), 0, -1):
            term = " ".join(words[start : start + size])
            candidates = _rank_candidates(term, vocabulary)
            if not candidates:
                continue
            match = (candidates[0]["match_score"], size, term, candidates)
            if best_match is None or match[:2] > best_match[:2]:
                best_match = match

        if best_match is None:
            start += 1
            continue

        _, size, term, candidates = best_match
        found.append({
            "text": term,
            "start": word_spans[start].start(),
            "end": word_spans[start + size - 1].end(),
            "candidates": candidates,
        })
        start += size

    for index, term in enumerate(found):
        next_start = found[index + 1]["start"] if index + 1 < len(found) else len(raw_text)
        details = raw_text[term["end"] : next_start].strip(" \t,;:-")
        term["prescription_details"] = re.sub(r"\s+(?:and|or)$", "", details, flags=re.IGNORECASE)

    return found


def fuzzy_candidates(db: Session, raw_text: str, limit: int = 3) -> list[dict]:
    term = extract_drug_term(raw_text)
    return _rank_candidates(term, medication_vocabulary(db), limit)


def resolve_term(db: Session, raw_text: str) -> list[dict]:
    """Return up to three candidate standard medicines for one manually entered term."""
    return fuzzy_candidates(db, raw_text)


def escape_like(text: str) -> str:
    """Escape LIKE wildcards so user input such as "50%" is matched literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def alias_matches(pattern: str):
    """EXISTS clause: the medication has an alias matching ``pattern``."""
    return exists().where(
        MedicationAlias.medication_id == Medication.id,
        MedicationAlias.alias.ilike(pattern, escape="\\"),
    )


def normalize_name(db: Session, raw_text: str) -> NormalizationResult:
    """Fuzzy-match a manually entered name after removing dosage and instruction text."""
    candidates = fuzzy_candidates(db, raw_text, limit=1)
    if not candidates:
        return NormalizationResult()
    candidate = candidates[0]
    return NormalizationResult(
        medication_id=candidate["medication_id"],
        match_score=candidate["match_score"],
    )
