"""Scoring configuration (QA-MNT-02).

All weights, thresholds and limits live in ``scoring_config.json`` (or a file
named by the ``DAWAWALA_SCORING_CONFIG`` environment variable), never in code.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

ENV_VAR = "DAWAWALA_SCORING_CONFIG"
DEFAULT_PATH = Path(__file__).with_name("scoring_config.json")
BAND_NAMES: Tuple[str, str, str, str] = ("Low", "Moderate", "High", "Critical")
CATEGORIES: Tuple[str, ...] = (
    "contraindication", "interaction", "cascade", "duplicate")


class ConfigError(ValueError):
    """Raised when the scoring configuration is missing or invalid."""


def _non_negative_int(data: Mapping, key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigError(f"'{key}' must be a non-negative integer")
    return value


@dataclass(frozen=True)
class ScoringConfig:
    score_max: int
    severity_points: Mapping[str, int]
    duplicate_points: int
    therapeutic_duplication_points: int
    cascade_points: int
    patient_factor_points: int
    patient_factor_max: int
    band_thresholds: Tuple[int, int, int]
    category_order: Tuple[str, ...]
    explanation_max_words: int
    kb_stale_days: int

    @classmethod
    def from_dict(cls, data: Mapping) -> "ScoringConfig":
        score_max = _non_negative_int(data, "score_max")
        if score_max == 0:
            raise ConfigError("'score_max' must be greater than zero")

        sev = data.get("severity_points")
        if not isinstance(sev, Mapping) or not sev:
            raise ConfigError("'severity_points' must be a non-empty object")
        severity = {}
        for name, pts in sev.items():
            if isinstance(pts, bool) or not isinstance(pts, int) or pts < 0:
                raise ConfigError(
                    f"severity '{name}' must map to a non-negative integer")
            severity[str(name).strip().lower()] = pts

        thresholds = data.get("band_thresholds")
        if (not isinstance(thresholds, (list, tuple))
                or len(thresholds) != 3
                or not all(isinstance(t, int) and not isinstance(t, bool)
                           for t in thresholds)):
            raise ConfigError("'band_thresholds' must be three integers")
        if not 0 < thresholds[0] < thresholds[1] < thresholds[2] <= score_max:
            raise ConfigError(
                "'band_thresholds' must be strictly increasing and within "
                "1..score_max")

        order = data.get("category_order")
        if (not isinstance(order, (list, tuple))
                or sorted(order) != sorted(CATEGORIES)):
            raise ConfigError(
                "'category_order' must list each category exactly once: "
                + ", ".join(CATEGORIES))

        max_words = _non_negative_int(data, "explanation_max_words")
        if max_words == 0:
            raise ConfigError("'explanation_max_words' must be > 0")

        return cls(
            score_max=score_max,
            severity_points=severity,
            duplicate_points=_non_negative_int(data, "duplicate_points"),
            therapeutic_duplication_points=_non_negative_int(
                data, "therapeutic_duplication_points"),
            cascade_points=_non_negative_int(data, "cascade_points"),
            patient_factor_points=_non_negative_int(
                data, "patient_factor_points"),
            patient_factor_max=_non_negative_int(data, "patient_factor_max"),
            band_thresholds=tuple(thresholds),  # type: ignore[arg-type]
            category_order=tuple(order),
            explanation_max_words=max_words,
            kb_stale_days=_non_negative_int(data, "kb_stale_days"),
        )

    @classmethod
    def from_file(cls, path) -> "ScoringConfig":
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"cannot read config '{path}': {exc}") from exc
        if not isinstance(data, Mapping):
            raise ConfigError("config root must be a JSON object")
        return cls.from_dict(data)


def load_default_config() -> ScoringConfig:
    """Load the config named by the environment, else the bundled defaults."""
    return ScoringConfig.from_file(os.environ.get(ENV_VAR) or DEFAULT_PATH)
