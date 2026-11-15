"""Public entry point: score, rank and explain a batch of warnings."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from .config import ScoringConfig, load_default_config
from .explanations import explain
from .models import PatientFactors, ScoredWarning, WarningInput
from .scoring import band_counts, rank_warnings, score_warning


def score_and_explain(
        warnings: Iterable[WarningInput],
        patient: Optional[PatientFactors] = None,
        config: Optional[ScoringConfig] = None) -> List[ScoredWarning]:
    """FR-11 + FR-13: every warning gets a score, band, factor list and
    explanation; the result is sorted highest score first."""
    config = config or load_default_config()
    patient = patient or PatientFactors()
    scored = [explain(score_warning(w, patient, config), config)
              for w in warnings]
    return rank_warnings(scored, config)


def analyse_payload(
        payload: Mapping[str, Any],
        config: Optional[ScoringConfig] = None) -> Dict[str, Any]:
    """JSON-in / JSON-out wrapper for the API layer.

    ``payload`` = {"warnings": [...], "patient_factors": {...}}
    """
    config = config or load_default_config()
    warnings = [WarningInput.from_dict(w) for w in payload.get("warnings", [])]
    patient = PatientFactors.from_dict(payload.get("patient_factors"))
    ranked = score_and_explain(warnings, patient, config)
    return {
        "warnings": [sw.to_dict() for sw in ranked],
        "band_counts": band_counts(ranked),
    }
