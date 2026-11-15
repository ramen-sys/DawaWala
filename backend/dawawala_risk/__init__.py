"""Dawawala risk-priority scoring (FR-11) and warning explanation (FR-13)."""
from .config import ConfigError, ScoringConfig, load_default_config
from .engine import analyse_payload, score_and_explain
from .explanations import explain, kb_notice
from .models import (
    Category, PatientFactors, ScoredWarning, ScoreFactor, WarningInput)
from .scoring import band_counts, band_for, rank_warnings, score_warning
from .templates import DISCLAIMER

__all__ = [
    "Category", "ConfigError", "DISCLAIMER", "PatientFactors", "ScoreFactor",
    "ScoredWarning", "ScoringConfig", "WarningInput", "analyse_payload",
    "band_counts", "band_for", "explain", "kb_notice", "load_default_config",
    "rank_warnings", "score_and_explain", "score_warning",
]
