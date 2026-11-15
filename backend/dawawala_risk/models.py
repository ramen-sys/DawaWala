"""Data types shared by scoring and explanation (FR-11, FR-13).

``WarningInput`` is the contract Member 3's safety engine hands to this
module; ``ScoredWarning`` is what the API returns to the front end.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple


class Category(str, Enum):
    CONTRAINDICATION = "contraindication"
    INTERACTION = "interaction"
    CASCADE = "cascade"
    DUPLICATE = "duplicate"

    @classmethod
    def parse(cls, value: Any) -> "Category":
        if isinstance(value, cls):
            return value
        text = str(value).strip().lower()
        if text == "ddi":  # SRS Table 5.1 / A.2 name for interactions
            text = "interaction"
        try:
            return cls(text)
        except ValueError:
            raise ValueError(f"unknown warning category: {value!r}") from None


# Patient-factor codes a KB rule may list as relevant (SRS Table 5.2).
AGE_65_PLUS = "age_65_plus"
KIDNEY_IMPAIRED = "kidney_impaired"
LIVER_IMPAIRED = "liver_impaired"
FACTOR_ORDER: Tuple[str, ...] = (AGE_65_PLUS, KIDNEY_IMPAIRED, LIVER_IMPAIRED)
FACTOR_LABELS = {
    AGE_65_PLUS: "age 65 or over",
    KIDNEY_IMPAIRED: "impaired kidney function",
    LIVER_IMPAIRED: "impaired liver function",
}

DUPLICATE_EXACT = "exact"
DUPLICATE_THERAPEUTIC = "therapeutic"

_AGE_VALUES = ("under_18", "18_64", "65_plus", "unknown")
_ORGAN_VALUES = ("normal", "impaired", "unknown")


def _check(value: str, allowed: Tuple[str, ...], name: str) -> str:
    text = str(value).strip().lower()
    if text not in allowed:
        raise ValueError(
            f"{name} must be one of {', '.join(allowed)}; got {value!r}")
    return text


@dataclass(frozen=True)
class PatientFactors:
    """Optional patient factors (FR-14). Everything defaults to unknown."""

    age_range: str = "unknown"
    kidney_function: str = "unknown"
    liver_function: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "age_range", _check(
            self.age_range, _AGE_VALUES, "age_range"))
        object.__setattr__(self, "kidney_function", _check(
            self.kidney_function, _ORGAN_VALUES, "kidney_function"))
        object.__setattr__(self, "liver_function", _check(
            self.liver_function, _ORGAN_VALUES, "liver_function"))

    @classmethod
    def from_dict(cls, data: Optional[Mapping]) -> "PatientFactors":
        data = data or {}
        return cls(
            age_range=data.get("age_range", "unknown"),
            kidney_function=data.get("kidney_function", "unknown"),
            liver_function=data.get("liver_function", "unknown"),
        )

    def active_factors(self) -> frozenset:
        """Factor codes that the user has supplied as 'applies'."""
        active = set()
        if self.age_range == "65_plus":
            active.add(AGE_65_PLUS)
        if self.kidney_function == "impaired":
            active.add(KIDNEY_IMPAIRED)
        if self.liver_function == "impaired":
            active.add(LIVER_IMPAIRED)
        return frozenset(active)


@dataclass(frozen=True)
class WarningInput:
    """A warning produced by the rule engine (FR-8, FR-9, FR-10, FR-12)."""

    category: Category
    medicines: Tuple[str, ...]
    rule_id: str
    kb_version: str
    severity: Optional[str] = None          # interaction / contraindication
    relevant_factors: Tuple[str, ...] = ()  # factors the KB rule lists
    duplicate_kind: str = DUPLICATE_EXACT   # duplicate only
    description: str = ""                   # KB description (optional)
    condition: str = ""                     # contraindication: factor text
    trigger: str = ""                       # cascade: triggering medicine
    symptom_pattern: str = ""               # cascade: new-symptom pattern
    downstream: str = ""                    # cascade: downstream medicine

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", Category.parse(self.category))
        meds = tuple(str(m).strip() for m in self.medicines if str(m).strip())
        if not meds:
            raise ValueError("a warning must name at least one medicine")
        object.__setattr__(self, "medicines", meds)
        if not str(self.rule_id).strip():
            raise ValueError("a warning must carry a rule_id (QA-EXP-04)")
        if not str(self.kb_version).strip():
            raise ValueError("a warning must carry a kb_version (QA-EXP-04)")
        unknown = set(self.relevant_factors) - set(FACTOR_ORDER)
        if unknown:
            raise ValueError(
                f"unknown relevant factor(s): {', '.join(sorted(unknown))}")
        object.__setattr__(
            self, "relevant_factors", tuple(self.relevant_factors))
        if self.category in (Category.INTERACTION, Category.CONTRAINDICATION):
            if not self.severity or not str(self.severity).strip():
                raise ValueError(
                    f"{self.category.value} warnings require a severity")
            object.__setattr__(
                self, "severity", str(self.severity).strip().lower())
        if self.category is Category.DUPLICATE:
            kind = str(self.duplicate_kind).strip().lower()
            if kind not in (DUPLICATE_EXACT, DUPLICATE_THERAPEUTIC):
                raise ValueError(f"unknown duplicate_kind: {kind!r}")
            object.__setattr__(self, "duplicate_kind", kind)

    @classmethod
    def from_dict(cls, data: Mapping) -> "WarningInput":
        return cls(
            category=data["category"],
            medicines=tuple(data["medicines"]),
            rule_id=data["rule_id"],
            kb_version=data["kb_version"],
            severity=data.get("severity"),
            relevant_factors=tuple(data.get("relevant_factors", ())),
            duplicate_kind=data.get("duplicate_kind", DUPLICATE_EXACT),
            description=data.get("description", "") or "",
            condition=data.get("condition", "") or "",
            trigger=data.get("trigger", "") or "",
            symptom_pattern=data.get("symptom_pattern", "") or "",
            downstream=data.get("downstream", "") or "",
        )

    @property
    def sort_name(self) -> str:
        """Alphabetical tie-break key (FR-11)."""
        return " + ".join(sorted(m.lower() for m in self.medicines))


@dataclass(frozen=True)
class ScoreFactor:
    """One itemized contribution to a score (QA-EXP-02)."""

    code: str
    label: str
    points: int

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "label": self.label, "points": self.points}


@dataclass(frozen=True)
class ScoredWarning:
    warning: WarningInput
    score: int
    raw_total: int
    capped: bool
    band: str
    factors: Tuple[ScoreFactor, ...]
    explanation: str = ""
    explanation_notes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # QA-EXP-02: the displayed items must sum to the score before the cap.
        if sum(f.points for f in self.factors) != self.raw_total:
            raise ValueError("factor points do not sum to raw_total")

    def to_dict(self) -> Dict[str, Any]:
        w = self.warning
        return {
            "category": w.category.value,
            "medicines": list(w.medicines),
            "rule_id": w.rule_id,
            "kb_version": w.kb_version,
            "severity": w.severity,
            "score": self.score,
            "raw_total": self.raw_total,
            "capped": self.capped,
            "band": self.band,
            "factors": [f.to_dict() for f in self.factors],
            "explanation": self.explanation,
        }
