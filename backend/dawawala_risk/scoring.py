"""Risk-priority scoring (FR-11, SRS Section 5.5).

score = sum(itemized factor points), capped at ``score_max``. Every point
comes from ``ScoringConfig`` (QA-MNT-02). The function is pure and has no
randomness, so identical input gives identical output (QA-REL-01).
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .config import BAND_NAMES, ScoringConfig
from .models import (
    DUPLICATE_THERAPEUTIC, FACTOR_LABELS, FACTOR_ORDER, Category,
    PatientFactors, ScoreFactor, ScoredWarning, WarningInput)


def band_for(score: int, config: ScoringConfig) -> str:
    """Low / Moderate / High / Critical from BAND_THRESHOLDS (A.1)."""
    index = sum(1 for bound in config.band_thresholds if score >= bound)
    return BAND_NAMES[index]


def _base_factor(w: WarningInput, config: ScoringConfig) -> ScoreFactor:
    if w.category in (Category.INTERACTION, Category.CONTRAINDICATION):
        points = config.severity_points.get(w.severity)
        if points is None:
            known = ", ".join(sorted(config.severity_points))
            raise ValueError(
                f"unknown severity {w.severity!r}; configured: {known}")
        kind = ("interaction" if w.category is Category.INTERACTION
                else "contraindication")
        return ScoreFactor(
            code=f"severity_{w.severity}",
            label=f"Rule severity ({kind}): {w.severity.capitalize()}",
            points=points)
    if w.category is Category.DUPLICATE:
        if w.duplicate_kind == DUPLICATE_THERAPEUTIC:
            return ScoreFactor(
                "therapeutic_duplication",
                "Possible therapeutic duplication (same drug class)",
                config.therapeutic_duplication_points)
        return ScoreFactor(
            "duplicate_medication",
            "Duplicate medication (same medicine entered more than once)",
            config.duplicate_points)
    return ScoreFactor(
        "cascade_pattern", "Possible prescribing-cascade pattern",
        config.cascade_points)


def _patient_factors(
        w: WarningInput, patient: PatientFactors,
        config: ScoringConfig) -> List[ScoreFactor]:
    """+N per supplied factor the rule lists, at most patient_factor_max.

    A factor is never counted twice for the same warning.
    """
    active = patient.active_factors()
    remaining = config.patient_factor_max
    out: List[ScoreFactor] = []
    for code in FACTOR_ORDER:
        if code not in w.relevant_factors or code not in active:
            continue
        points = min(config.patient_factor_points, remaining)
        if points <= 0:
            break
        out.append(ScoreFactor(
            f"patient_{code}", f"Patient factor: {FACTOR_LABELS[code]}",
            points))
        remaining -= points
    return out


def score_warning(
        w: WarningInput,
        patient: Optional[PatientFactors] = None,
        config: Optional[ScoringConfig] = None) -> ScoredWarning:
    """Score one warning and return it with its itemized breakdown."""
    if config is None:
        from .config import load_default_config
        config = load_default_config()
    patient = patient or PatientFactors()
    factors = [_base_factor(w, config)]
    factors.extend(_patient_factors(w, patient, config))
    raw_total = sum(f.points for f in factors)
    score = min(raw_total, config.score_max)
    return ScoredWarning(
        warning=w, score=score, raw_total=raw_total,
        capped=raw_total > config.score_max,
        band=band_for(score, config), factors=tuple(factors))


def sort_key(sw: ScoredWarning, config: ScoringConfig):
    """Score desc, then category order, then alphabetical (FR-11).

    ``rule_id`` is a final tie-break so the order is fully deterministic.
    """
    rank = config.category_order.index(sw.warning.category.value)
    return (-sw.score, rank, sw.warning.sort_name, sw.warning.rule_id)


def rank_warnings(
        scored: Iterable[ScoredWarning],
        config: ScoringConfig) -> List[ScoredWarning]:
    return sorted(scored, key=lambda sw: sort_key(sw, config))


def band_counts(scored: Iterable[ScoredWarning]) -> dict:
    """Counts per severity band for the results summary (FR-15)."""
    counts = {name: 0 for name in BAND_NAMES}
    for sw in scored:
        counts[sw.band] += 1
    return counts
