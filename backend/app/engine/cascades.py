"""FR-12: Prescribing-cascade detection.

A cascade rule matches when the list contains a triggering medication and a
medication from the rule's downstream pattern (by name or by drug class).
Example: amlodipine (trigger) -> ankle swelling -> furosemide (downstream).

The engine cannot know which medicine was prescribed first, so every match
is a *possible* cascade; the wording must never present it as a diagnosis.
One warning is raised per matched rule, listing every trigger and
downstream medication found, to avoid near-identical repeated warnings.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .models import (
    CASCADE,
    CascadeRule,
    KnowledgeBase,
    SafetyWarning,
    format_factors,
    matched_factors,
)


def _members(med_ids: list[int], meds: frozenset[int], classes: frozenset[str],
             kb: KnowledgeBase) -> list[int]:
    return [
        m for m in med_ids
        if m in meds or classes.intersection(kb.medications[m].classes)
    ]


def _match(rule: CascadeRule, med_ids: list[int], kb: KnowledgeBase):
    triggers = _members(med_ids, rule.trigger_medications, rule.trigger_classes, kb)
    downstream = _members(med_ids, rule.downstream_medications, rule.downstream_classes, kb)
    # A cascade needs two different medicines.
    if not any(t != d for t in triggers for d in downstream):
        return None
    return tuple(triggers), tuple(downstream)


def detect_cascades(
    medication_ids: Iterable[int],
    kb: KnowledgeBase,
    patient: Mapping[str, str],
) -> list[SafetyWarning]:
    med_ids = sorted(set(medication_ids))
    warnings = []
    for rule in kb.cascades:  # already sorted by rule_id
        found = _match(rule, med_ids, kb)
        if found is None:
            continue
        triggers, downstream = found
        involved = tuple(sorted(set(triggers) | set(downstream)))
        warnings.append(
            SafetyWarning(
                category=CASCADE,
                rule_id=rule.rule_id,
                medication_ids=involved,
                medication_names=kb.names(involved),
                severity=None,
                description=rule.description,
                relevant_factors=format_factors(rule.relevant_factors),
                matched_factors=matched_factors(rule.relevant_factors, patient),
                kb_version=kb.version,
                details={
                    "trigger_ids": list(triggers),
                    "trigger_names": list(kb.names(triggers)),
                    "symptom_pattern": rule.symptom_pattern,
                    "downstream_ids": list(downstream),
                    "downstream_names": list(kb.names(downstream)),
                },
            )
        )
    return warnings
