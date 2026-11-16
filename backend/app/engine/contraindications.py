"""FR-10: Contraindication detection.

Each confirmed medication's contraindication records, and those of its active
ingredients (a combination product containing ibuprofen inherits ibuprofen's
kidney rule), are compared with the patient's risk factors (FR-14). For each
record there are three outcomes:

  * factor known and matches   -> warning
  * factor unknown/not given   -> "Not assessed" entry (never silently dropped)
  * factor known, no match     -> nothing
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .models import (
    CONTRAINDICATION,
    UNKNOWN,
    ContraindicationRule,
    KnowledgeBase,
    NotAssessed,
    SafetyWarning,
    format_factors,
    matched_factors,
)


def _rules_for(med_id: int, kb: KnowledgeBase) -> list[tuple[ContraindicationRule, int]]:
    """(rule, medication the rule is written for), one per rule id."""
    found: dict[str, tuple[ContraindicationRule, int]] = {}
    for source in kb.with_components(med_id):
        for rule in kb.contraindications.get(source, ()):
            found.setdefault(rule.rule_id, (rule, source))
    return [found[rule_id] for rule_id in sorted(found)]


def detect_contraindications(
    medication_ids: Iterable[int],
    kb: KnowledgeBase,
    patient: Mapping[str, str],
) -> tuple[list[SafetyWarning], list[NotAssessed]]:
    warnings: list[SafetyWarning] = []
    not_assessed: list[NotAssessed] = []

    for med_id in sorted(set(medication_ids)):
        name = kb.name(med_id)
        for rule, source in _rules_for(med_id, kb):
            value = patient.get(rule.factor, UNKNOWN)
            if value == UNKNOWN:
                not_assessed.append(NotAssessed(rule.rule_id, med_id, name, rule.factor))
            elif value == rule.value:
                details = {"condition": f"{rule.factor}:{rule.value}"}
                if source != med_id:
                    details["via"] = kb.name(source)
                warnings.append(
                    SafetyWarning(
                        category=CONTRAINDICATION,
                        rule_id=rule.rule_id,
                        medication_ids=(med_id,),
                        medication_names=(name,),
                        severity=rule.severity,
                        description=rule.description,
                        relevant_factors=format_factors(rule.relevant_factors),
                        matched_factors=matched_factors(rule.relevant_factors, patient),
                        kb_version=kb.version,
                        details=details,
                    )
                )

    return warnings, not_assessed
