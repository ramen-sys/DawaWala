"""Single entry point for the safety engine.

The API layer calls analyze() with a confirmed list (FR-7 / BR-01 must
already be enforced by the caller) and the list's risk factors (FR-14).
The result goes to scoring (FR-11) and explanation (FR-13).
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .cascades import detect_cascades
from .contraindications import detect_contraindications
from .duplicates import detect_duplicates
from .interactions import detect_interactions
from .models import (
    CATEGORY_ORDER,
    UNKNOWN,
    AnalysisResult,
    ConfirmedItem,
    KnowledgeBase,
    NotAnalysed,
)


def normalise_risk_factors(
    risk_factors: Mapping[str, str] | None, kb: KnowledgeBase
) -> dict[str, str]:
    """Validate risk factors against the KB vocabulary.

    Missing factors count as "unknown". Raises ValueError on a factor or
    value the knowledge base does not define, so bad input is never
    silently ignored.
    """
    patient = {name: UNKNOWN for name in kb.risk_factors}
    for name, value in (risk_factors or {}).items():
        if name not in kb.risk_factors:
            raise ValueError(f"Unknown risk factor: {name!r}")
        value = (value or UNKNOWN).strip().lower()
        if value != UNKNOWN and value not in kb.risk_factors[name]:
            allowed = ", ".join(kb.risk_factors[name] + (UNKNOWN,))
            raise ValueError(f"Invalid value {value!r} for {name}; expected one of: {allowed}")
        patient[name] = value
    return patient


def analyze(
    items: Sequence[ConfirmedItem],
    kb: KnowledgeBase,
    risk_factors: Mapping[str, str] | None = None,
) -> AnalysisResult:
    patient = normalise_risk_factors(risk_factors, kb)

    recognised: list[ConfirmedItem] = []
    not_analysed: list[NotAnalysed] = []
    for item in items:
        if item.medication_id is None:
            not_analysed.append(NotAnalysed(item.item_id, item.entered_text, "unrecognised"))
        elif item.medication_id not in kb.medications:
            # Should not happen for a list confirmed against this KB version,
            # but never drop a medicine silently (SAF-03).
            not_analysed.append(
                NotAnalysed(item.item_id, item.entered_text, "not_in_knowledge_base")
            )
        else:
            recognised.append(item)

    med_ids = [item.medication_id for item in recognised]
    contra_warnings, not_assessed = detect_contraindications(med_ids, kb, patient)
    warnings = (
        detect_interactions(med_ids, kb, patient)
        + detect_duplicates(recognised, kb)
        + contra_warnings
        + detect_cascades(med_ids, kb, patient)
    )

    # Deterministic order (QA-REL-01). Final ranking by score is done by
    # the scoring module (FR-11); this only guarantees a stable input order.
    warnings.sort(key=lambda w: (CATEGORY_ORDER[w.category], w.medication_names, w.rule_id))
    not_assessed.sort(key=lambda n: (n.medication_name, n.missing_factor, n.rule_id))
    not_analysed.sort(key=lambda n: (n.entered_text.lower(), str(n.item_id)))

    return AnalysisResult(
        warnings=warnings,
        not_assessed=not_assessed,
        not_analysed=not_analysed,
        kb_version=kb.version,
        kb_updated=kb.updated,
    )
