"""FR-11: patient-risk-priority scoring (SRS Section 5.5, Table 5.2).

The score is the sum of itemized factor points, capped at SCORE_MAX. The itemized list is
always returned with the score and adds up to it before the cap, so the score is never shown
without the factors that produced it (QA-EXP-02). Weights come from settings (QA-MNT-02).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.engine import SafetyWarning
from app.engine.models import CASCADE, CATEGORY_ORDER, CONTRAINDICATION, DDI, DUPLICATE
from app.models.enums import SeverityBand

# Patient factors that earn the modifier (Table 5.2): age 65 or over, impaired kidney or liver function.
MODIFIER_FACTORS = {
    "age_range:65_plus": "Age 65 or over",
    "kidney_function:impaired": "Impaired kidney function",
    "liver_function:impaired": "Impaired liver function",
}


def _severity_points() -> dict[str, int]:
    return {
        "Minor": settings.SCORE_SEVERITY_MINOR,
        "Moderate": settings.SCORE_SEVERITY_MODERATE,
        "Major": settings.SCORE_SEVERITY_MAJOR,
        "Contraindicated": settings.SCORE_SEVERITY_CONTRAINDICATED,
    }


@dataclass(frozen=True)
class Score:
    score: int
    band: SeverityBand
    factors: list[dict]  # [{"factor": "...", "points": n}, ...]


def band_for(score: int) -> SeverityBand:
    moderate, high, critical = settings.band_thresholds
    if score >= critical:
        return SeverityBand.CRITICAL
    if score >= high:
        return SeverityBand.HIGH
    if score >= moderate:
        return SeverityBand.MODERATE
    return SeverityBand.LOW


def score_warning(warning: SafetyWarning) -> Score:
    factors: list[dict] = []
    if warning.category in (DDI, CONTRAINDICATION):
        kind = "interaction" if warning.category == DDI else "contraindication"
        factors.append({"factor": f"Rule severity ({kind}): {warning.severity}",
                        "points": _severity_points()[warning.severity]})
    elif warning.category == DUPLICATE:
        if warning.details.get("kind") == "therapeutic":
            factors.append({"factor": "Possible therapeutic duplication", "points": settings.SCORE_THERAPEUTIC_DUPLICATE})
        else:
            factors.append({"factor": "Duplicate medication", "points": settings.SCORE_DUPLICATE})
    elif warning.category == CASCADE:
        factors.append({"factor": "Prescribing-cascade pattern", "points": settings.SCORE_CASCADE})
    else:  # pragma: no cover - the engine only produces the four categories
        raise ValueError(f"Unknown warning category {warning.category!r}")

    # +5 for each relevant factor the patient has, at most +15; the same factor never counts twice.
    budget = settings.SCORE_PATIENT_FACTOR_MAX
    for token in dict.fromkeys(warning.matched_factors):
        label = MODIFIER_FACTORS.get(token)
        if label is None or budget <= 0:
            continue
        points = min(settings.SCORE_PATIENT_FACTOR, budget)
        budget -= points
        factors.append({"factor": f"Patient factor: {label}", "points": points})

    total = min(settings.SCORE_MAX, sum(f["points"] for f in factors))
    return Score(total, band_for(total), factors)


def ranking_key(warning: SafetyWarning, score: Score) -> tuple:
    """FR-11 order: highest score first, then category (contraindication, DDI, cascade, duplicate),
    then alphabetically by medication names; rule id last so the order is always deterministic."""
    names = tuple(n.lower() for n in warning.medication_names)
    return (-score.score, CATEGORY_ORDER[warning.category], names, warning.rule_id)
