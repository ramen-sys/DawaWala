"""Shared test helpers."""
import json

from dawawala_risk.config import DEFAULT_PATH, ScoringConfig
from dawawala_risk.models import WarningInput


def default_data():
    with open(DEFAULT_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def make_config(**overrides):
    data = default_data()
    data.update(overrides)
    return ScoringConfig.from_dict(data)


def ddi(severity="major", meds=("Aspirin", "Warfarin"), rule="DDI-1",
        factors=(), **kw):
    return WarningInput("interaction", meds, rule, "KB-1.0.0", severity,
                        tuple(factors), **kw)


def contra(severity="major", meds=("Metformin",), rule="CI-1", factors=(),
           **kw):
    return WarningInput("contraindication", meds, rule, "KB-1.0.0", severity,
                        tuple(factors), **kw)


def dup(meds=("Paracetamol",), rule="DUP-1", kind="exact", **kw):
    return WarningInput("duplicate", meds, rule, "KB-1.0.0",
                        duplicate_kind=kind, **kw)


def cascade(meds=("Amlodipine", "Furosemide"), rule="CAS-1", factors=(),
            **kw):
    return WarningInput("cascade", meds, rule, "KB-1.0.0",
                        relevant_factors=tuple(factors), **kw)
