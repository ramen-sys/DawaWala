"""Dawawala safety engine: FR-8, FR-9, FR-10 and FR-12.

Typical use from the API layer:

    from app.engine import ConfirmedItem, analyze, load_kb

    kb = load_kb()                       # load once at start-up
    result = analyze(items, kb, {"kidney_function": "impaired"})
    payload = result.to_dict()           # JSON-ready
"""

from .analyze import analyze, normalise_risk_factors
from .loader import DEFAULT_KB_DIR, KBValidationError, load_kb
from .models import (
    AnalysisResult,
    ConfirmedItem,
    KnowledgeBase,
    NotAnalysed,
    NotAssessed,
    SafetyWarning,
)

__all__ = [
    "AnalysisResult", "ConfirmedItem", "DEFAULT_KB_DIR", "KBValidationError",
    "KnowledgeBase", "NotAnalysed", "NotAssessed", "SafetyWarning",
    "analyze", "load_kb", "normalise_risk_factors",
]
