"""Exact-match lookup of typed names against the knowledge base.

This is the interface FR-3 hands names to. The fuzzy matcher (FR-6, ocr/ module) is expected
to replace ``normalize_name`` with the same signature; until then only exact standard-name or
alias matches are resolved and everything else stays pending (match_score = None).

Both ``medications.standard_name`` and ``medication_aliases.alias`` have pg_trgm GIN indexes,
which PostgreSQL uses for ILIKE here and for similarity() / ``%`` in the fuzzy matcher.
"""

import re
from dataclasses import dataclass

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Medication, MedicationAlias
from app.models.enums import ConfidenceLabel

_NON_DRUG_TOKENS = re.compile(
    r"\b(\d+(\.\d+)?\s*(mg|mcg|g|ml|iu|%)?|tab(let)?s?|cap(sule)?s?|syrup|susp(ension)?|"
    r"inj(ection)?|cream|ointment|drops?|oral|od|bd|tds|qid|hs|sr|xr|er|mr)\b",
    re.IGNORECASE,
)


@dataclass
class NormalizationResult:
    medication_id: int | None = None
    match_score: int | None = None


def extract_drug_term(raw_text: str) -> str:
    term = _NON_DRUG_TOKENS.sub(" ", raw_text)
    return " ".join(term.split()).strip(" -,.;:/")


def confidence_label(match_score: int | None) -> ConfidenceLabel | None:
    """FR-6 thresholds. None means the item has not been normalized yet."""
    if match_score is None:
        return None
    if match_score >= settings.MATCH_HIGH:
        return ConfidenceLabel.HIGH
    if match_score >= settings.MATCH_LOW:
        return ConfidenceLabel.LOW
    return ConfidenceLabel.UNRECOGNISED


def escape_like(text: str) -> str:
    """Escape LIKE wildcards so user input such as "50%" is matched literally (use with escape="\\")."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def alias_matches(pattern: str):
    """EXISTS clause: the medication has an alias matching ``pattern`` (case-insensitive ILIKE)."""
    return exists().where(
        MedicationAlias.medication_id == Medication.id,
        MedicationAlias.alias.ilike(pattern, escape="\\"),
    )


def normalize_name(db: Session, raw_text: str) -> NormalizationResult:
    """Resolve a typed name to a medication if it equals a standard name or an alias (any case)."""
    term = extract_drug_term(raw_text)
    if not term:
        return NormalizationResult()

    pattern = escape_like(term)  # no wildcards added: ILIKE without % is a case-insensitive equality
    med_id = db.scalar(
        select(Medication.id)
        .where(or_(Medication.standard_name.ilike(pattern, escape="\\"), alias_matches(pattern)))
        # Prefer a standard-name hit over an alias hit, then the lowest ID, so results are deterministic.
        .order_by(~Medication.standard_name.ilike(pattern, escape="\\"), Medication.id)
        .limit(1)
    )
    if med_id is None:
        return NormalizationResult()
    return NormalizationResult(medication_id=med_id, match_score=100)
