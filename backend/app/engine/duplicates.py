"""FR-9: Duplicate medication detection.

Two levels:
  * exact duplicate - the same standard medication appears more than once,
    usually under different brand names (e.g. Panadol and Calpol are both
    paracetamol). rule_id "DUP-EXACT".
  * possible therapeutic duplication - two *different* medications share a
    drug class marked duplication_relevant in drug_classes.csv (e.g.
    ibuprofen and naproxen are both NSAIDs). rule_id "DUP-CLASS:<class>".

Both use category "duplicate"; details["kind"] tells them apart so scoring
can apply 30 or 15 points (SRS Table 5.2).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import DUPLICATE, ConfirmedItem, KnowledgeBase, SafetyWarning


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
            warnings.append(
                SafetyWarning(
                    category=DUPLICATE,
                    rule_id="DUP-EXACT",
                    medication_ids=(med_id,),
                    medication_names=(name,),
                    severity=None,
                    description=f"{name} appears {len(texts)} times in this list.",
                    relevant_factors=(),
                    matched_factors=(),
                    kb_version=kb.version,
                    details={"kind": "exact", "entered_as": texts},
                )
            )

    members: dict[str, set[int]] = defaultdict(set)
    for med_id in entered_as:
        for cls in kb.medications[med_id].classes:
            if kb.classes[cls].duplication_relevant:
                members[cls].add(med_id)

    for cls in sorted(members):
        med_ids = tuple(sorted(members[cls]))
        if len(med_ids) > 1:
            warnings.append(
                SafetyWarning(
                    category=DUPLICATE,
                    rule_id=f"DUP-CLASS:{cls}",
                    medication_ids=med_ids,
                    medication_names=kb.names(med_ids),
                    severity=None,
                    description=f"These medicines all belong to the same group ({cls}).",
                    relevant_factors=(),
                    matched_factors=(),
                    kb_version=kb.version,
                    details={"kind": "therapeutic", "drug_class": cls},
                )
            )

    return warnings
