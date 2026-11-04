"""Data types used by the safety engine (FR-8, FR-9, FR-10, FR-12).

The engine works on plain Python objects so it can be developed and tested
without the database, the API or the frontend. loader.py builds these
objects from the CSV fixtures. db_loader.py builds the same objects from
PostgreSQL, and the detectors do not change.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

# Severity scale shared by interaction and contraindication records.
# Must match the scoring table in SRS Section 5.5 exactly.
SEVERITIES = ("Minor", "Moderate", "Major", "Contraindicated")

# A risk factor the user has not supplied is always "unknown" (FR-14).
UNKNOWN = "unknown"

# Warning categories (SRS Appendix A.2, warning.category).
DDI = "DDI"
DUPLICATE = "duplicate"
CONTRAINDICATION = "contraindication"
CASCADE = "cascade"

# Fixed category order used to make engine output deterministic
# (QA-REL-01). Same order as the FR-11 tie-break.
CATEGORY_ORDER = {CONTRAINDICATION: 0, DDI: 1, CASCADE: 2, DUPLICATE: 3}

# A risk-factor condition such as ("kidney_function", "impaired").
Factor = tuple[str, str]


def format_factors(factors: tuple[Factor, ...]) -> tuple[str, ...]:
    """Turn (factor, value) pairs into "factor:value" strings."""
    return tuple(f"{name}:{value}" for name, value in factors)


def matched_factors(
    factors: tuple[Factor, ...], patient: Mapping[str, str]
) -> tuple[str, ...]:
    """Return the rule's relevant factors that this patient actually has."""
    return format_factors(
        tuple((name, value) for name, value in factors if patient.get(name) == value)
    )


# --------------------------------------------------------------------------
# Knowledge-base records
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DrugClass:
    name: str
    # True if two different drugs in this class should raise a
    # "possible therapeutic duplication" warning (FR-9).
    duplication_relevant: bool


@dataclass(frozen=True)
class Medication:
    medication_id: int
    standard_name: str
    classes: tuple[str, ...]
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class InteractionRule:
    rule_id: str
    drug_a: int  # always stored so that drug_a < drug_b
    drug_b: int
    severity: str
    description: str
    relevant_factors: tuple[Factor, ...]
    source: str


@dataclass(frozen=True)
class ContraindicationRule:
    rule_id: str
    medication_id: int
    factor: str  # the patient factor this record depends on
    value: str  # the value that makes it apply, e.g. "impaired"
    severity: str
    description: str
    relevant_factors: tuple[Factor, ...]  # extra factors, never the condition itself
    source: str


@dataclass(frozen=True)
class CascadeRule:
    rule_id: str
    trigger_medications: frozenset[int]
    trigger_classes: frozenset[str]
    symptom_pattern: str
    downstream_medications: frozenset[int]
    downstream_classes: frozenset[str]
    description: str
    relevant_factors: tuple[Factor, ...]
    source: str


@dataclass(frozen=True)
class KnowledgeBase:
    version: str
    updated: str  # ISO date, e.g. "2026-10-20" (SAF-07)
    medications: Mapping[int, Medication]
    classes: Mapping[str, DrugClass]
    # factor name -> allowed values (not including "unknown")
    risk_factors: Mapping[str, tuple[str, ...]]
    # (drug_a, drug_b) with drug_a < drug_b -> one or more records
    interactions: Mapping[tuple[int, int], tuple[InteractionRule, ...]]
    contraindications: Mapping[int, tuple[ContraindicationRule, ...]]
    cascades: tuple[CascadeRule, ...]

    def interactions_for(self, a: int, b: int) -> tuple[InteractionRule, ...]:
        """Interaction records for an unordered pair of medications."""
        key = (a, b) if a < b else (b, a)
        return self.interactions.get(key, ())

    def name(self, medication_id: int) -> str:
        return self.medications[medication_id].standard_name

    def names(self, medication_ids: tuple[int, ...]) -> tuple[str, ...]:
        return tuple(self.name(m) for m in medication_ids)


# --------------------------------------------------------------------------
# Engine input
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfirmedItem:
    """One item of a user-confirmed medication list (FR-7).

    medication_id is None for an item the user chose to "keep as
    unrecognised"; such items are reported under "Not analysed".
    """

    item_id: str | int
    medication_id: int | None
    entered_text: str


# --------------------------------------------------------------------------
# Engine output
# --------------------------------------------------------------------------


@dataclass
class SafetyWarning:
    """A single finding handed to scoring (FR-11) and explanation (FR-13).

    severity is set for DDI and contraindication warnings (from the record).
    It is None for duplicate and cascade warnings, which are scored by
    category instead (SRS Table 5.2).
    """

    category: str
    rule_id: str
    medication_ids: tuple[int, ...]
    medication_names: tuple[str, ...]
    severity: str | None
    description: str
    relevant_factors: tuple[str, ...]  # factors the rule lists as relevant
    matched_factors: tuple[str, ...]  # the subset this patient has
    kb_version: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NotAssessed:
    """A contraindication check skipped because a patient factor is unknown (FR-10)."""

    rule_id: str
    medication_id: int
    medication_name: str
    missing_factor: str


@dataclass(frozen=True)
class NotAnalysed:
    """A list item the engine could not check (FR-15, SAF-03)."""

    item_id: str | int
    entered_text: str
    reason: str  # "unrecognised" or "not_in_knowledge_base"


@dataclass
class AnalysisResult:
    warnings: list[SafetyWarning]
    not_assessed: list[NotAssessed]
    not_analysed: list[NotAnalysed]
    kb_version: str
    kb_updated: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
