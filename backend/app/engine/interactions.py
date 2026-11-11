"""FR-8: Drug-drug interaction detection.

Every unordered pair of distinct confirmed medications is looked up in the
interaction records. A combination product is checked through its active
ingredients too, so "Ibuprofen + Pseudoephedrine" with warfarin raises the
ibuprofen-warfarin rule. A pair with no record produces no warning; that never
means the pair is "safe" (SAF-03), only that the knowledge base has no rule.
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable, Mapping

from .models import DDI, InteractionRule, KnowledgeBase, SafetyWarning, format_factors, matched_factors


def _rules_for(a: int, b: int, kb: KnowledgeBase) -> list[tuple[InteractionRule, tuple[int, int]]]:
    """Rules between a and b, directly or through their ingredients, one per rule id."""
    found: dict[str, tuple[InteractionRule, tuple[int, int]]] = {}
    for x in kb.with_components(a):
        for y in kb.with_components(b):
            if x == y:
                continue  # a shared ingredient is a duplicate (FR-9), not an interaction
            for rule in kb.interactions_for(x, y):
                found.setdefault(rule.rule_id, (rule, (x, y)))
    return [found[rule_id] for rule_id in sorted(found)]


def detect_interactions(
    medication_ids: Iterable[int],
    kb: KnowledgeBase,
    patient: Mapping[str, str],
) -> list[SafetyWarning]:
    warnings = []
    # set() removes exact duplicates (FR-9 handles those), sorted() keeps
    # the output identical between runs (QA-REL-01). With the 30-medication
    # limit this is at most 435 pairs (PERF-01).
    for a, b in combinations(sorted(set(medication_ids)), 2):
        for rule, via in _rules_for(a, b, kb):
            details = {}
            if via != (a, b):
                # Tell the explanation which ingredients the rule is really about.
                details["via"] = list(kb.names(via))
            warnings.append(
                SafetyWarning(
                    category=DDI,
                    rule_id=rule.rule_id,
                    medication_ids=(a, b),
                    medication_names=kb.names((a, b)),
                    severity=rule.severity,
                    description=rule.description,
                    relevant_factors=format_factors(rule.relevant_factors),
                    matched_factors=matched_factors(rule.relevant_factors, patient),
                    kb_version=kb.version,
                    details=details,
                )
            )
    return warnings
