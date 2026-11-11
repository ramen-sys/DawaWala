"""FR-9: Duplicate medication detection.

Three cases, all with category "duplicate":
  * exact duplicate - the same standard medication appears more than once,
    usually under different brand names (e.g. Panadol and Calpol are both
    paracetamol). rule_id "DUP-EXACT", kind "exact".
  * shared active ingredient - two *different* products contain the same
    ingredient (e.g. Panadol and "Paracetamol + Caffeine"), so the patient may
    take a double dose. rule_id "DUP-INGREDIENT:<ingredient>", kind "exact",
    because the risk is the same as taking one medicine twice.
  * possible therapeutic duplication - two *different* medications share a
    drug class marked duplication_relevant (e.g. ibuprofen and naproxen are
    both NSAIDs). rule_id "DUP-CLASS:<class>", kind "therapeutic". Skipped when
    every pair in the group is already reported as a shared ingredient.

details["kind"] lets scoring apply 30 (exact) or 15 (therapeutic) points
(SRS Table 5.2).
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable

from .models import DUPLICATE, ConfirmedItem, KnowledgeBase, SafetyWarning


def _warning(kb: KnowledgeBase, rule_id: str, med_ids: tuple[int, ...], description: str,
             details: dict) -> SafetyWarning:
    return SafetyWarning(
        category=DUPLICATE,
        rule_id=rule_id,
        medication_ids=med_ids,
        medication_names=kb.names(med_ids),
        severity=None,
        description=description,
        relevant_factors=(),
        matched_factors=(),
        kb_version=kb.version,
        details=details,
    )


def detect_duplicates(items: Iterable[ConfirmedItem], kb: KnowledgeBase) -> list[SafetyWarning]:
    """items must contain only recognised medications (medication_id set)."""
    entered_as: dict[int, list[str]] = defaultdict(list)
    for item in items:
        entered_as[item.medication_id].append(item.entered_text)

    warnings = []

    for med_id in sorted(entered_as):
        texts = sorted(entered_as[med_id], key=str.lower)
        if len(texts) > 1:
            name = kb.name(med_id)
            warnings.append(_warning(
                kb, "DUP-EXACT", (med_id,), f"{name} appears {len(texts)} times in this list.",
                {"kind": "exact", "entered_as": texts},
            ))

    # Shared active ingredients between different products.
    by_ingredient: dict[str, set[int]] = defaultdict(set)
    display: dict[str, str] = {}
    for med_id in entered_as:
        for ingredient in kb.medications[med_id].ingredients:
            key = ingredient.lower()
            by_ingredient[key].add(med_id)
            display.setdefault(key, ingredient)
    sharing: set[tuple[int, int]] = set()
    for key in sorted(by_ingredient):
        med_ids = tuple(sorted(by_ingredient[key]))
        if len(med_ids) > 1:
            sharing.update(combinations(med_ids, 2))
            ingredient = display[key]
            warnings.append(_warning(
                kb, f"DUP-INGREDIENT:{ingredient}", med_ids,
                f"These medicines all contain {ingredient}, so together they may give too much of it.",
                {"kind": "exact", "ingredient": ingredient},
            ))

    members: dict[str, set[int]] = defaultdict(set)
    for med_id in entered_as:
        for cls in kb.medications[med_id].classes:
            if kb.classes[cls].duplication_relevant:
                members[cls].add(med_id)

    for cls in sorted(members):
        med_ids = tuple(sorted(members[cls]))
        if len(med_ids) > 1 and not set(combinations(med_ids, 2)) <= sharing:
            warnings.append(_warning(
                kb, f"DUP-CLASS:{cls}", med_ids,
                f"These medicines all belong to the same group ({cls}).",
                {"kind": "therapeutic", "drug_class": cls},
            ))

    return warnings
