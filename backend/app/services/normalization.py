"""Exact name normalization and fuzzy medication-alias candidate lookup.

List creation uses ``normalize_name`` for exact standard-name and alias matches. The
confirmation flow uses ``resolve_term`` to retrieve up to three fuzzy alias candidates.
Both lookup paths use indexed knowledge-base name columns.
"""
import re
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Medication, MedicationAlias
from app.models.enums import ConfidenceLabel

FUZZY_TRGM_CUTOFF = 0.2  # loose retrieval; the real decision uses rapidfuzz below

def resolve_term(db: Session, raw_text: str) -> list[dict]:
    """Return up to three fuzzy alias candidates for the confirmation flow."""
    return fuzzy_candidates(db, raw_text)


def fuzzy_candidates(db: Session, raw_text: str, limit: int = 3) -> list[dict]:
    term = extract_drug_term(raw_text)
    if not term:
        return []

    rows = db.execute(
        select(MedicationAlias.alias, Medication.id, Medication.standard_name)
        .join(Medication, Medication.id == MedicationAlias.medication_id)
        .where(func.similarity(MedicationAlias.alias, term) >= FUZZY_TRGM_CUTOFF)
    ).all()

    # Score each alias on FR-6's 0-100 scale and keep the best alias per medication.
    best: dict[int, dict] = {}
    for alias, med_id, standard in rows:
        score = round(fuzz.ratio(term.lower(), alias.lower()))
        if score < settings.MATCH_LOW:
            continue
        if med_id not in best or score > best[med_id]["match_score"]:
            best[med_id] = {
                "medication_id": med_id,
                "standard_name": standard,
                "matched_alias": alias,
                "match_score": score,
                "label": confidence_label(score).value,
            }

    ranked = sorted(best.values(), key=lambda c: (-c["match_score"], c["medication_id"]))
    return ranked[:limit]

_NON_DRUG_TOKENS = re.compile(
    r"\b(\d+(\.\d+)?\s*(mg|mcg|g|ml|iu|%)?|tab(let)?s?|cap(sule)?s?|syrup|susp(ension)?|"
    r"inj(ection)?|cream|ointment|drops?|oral|od|bd|tds|qid|hs|sr|xr|er|mr)\b",
    re.IGNORECASE,
)

_STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%)", re.IGNORECASE)


def extract_strengths(raw_text: str) -> list[str]:
    return [f"{num}{unit.lower()}" for num, unit in _STRENGTH.findall(raw_text)]


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
