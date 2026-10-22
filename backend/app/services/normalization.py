"""Exact-match lookup of typed names against the knowledge base.

This is the interface FR-3 hands names to. The fuzzy matcher (FR-6, ocr/ module) is expected
to replace ``normalize_name`` with the same signature; until then only exact standard-name or
alias matches are resolved and everything else stays pending (match_score = None).
"""

import re
from dataclasses import dataclass

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Medication
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


def alias_matches(predicate_factory):
    """EXISTS (SELECT 1 FROM unnest(medications.aliases) a WHERE <predicate on a>)."""
    alias = func.unnest(Medication.aliases).table_valued("value").render_derived(name="a")
    return exists(select(1).select_from(alias).where(predicate_factory(func.lower(alias.c.value))))


def normalize_name(db: Session, raw_text: str) -> NormalizationResult:
    term = extract_drug_term(raw_text).lower()
    if not term:
        return NormalizationResult()

    med_id = db.scalar(
        select(Medication.id)
        .where(or_(func.lower(Medication.standard_name) == term, alias_matches(lambda a: a == term)))
        .order_by(func.lower(Medication.standard_name) != term, Medication.id)
        .limit(1)
    )
    if med_id is None:
        return NormalizationResult()
    return NormalizationResult(medication_id=med_id, match_score=100)
