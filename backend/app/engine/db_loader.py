"""Build the safety-engine knowledge base from the database tables.

The detectors keep using the in-memory records from models.py. This module
only translates medications, drug_interactions, contraindications and
cascade_rules into those records (BR-05: rules stay data).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FACTOR_VALUES, Severity
from app.models.knowledge_base import CascadeRule as CascadeRuleRow
from app.models.knowledge_base import Contraindication as ContraindicationRow
from app.models.knowledge_base import DrugInteraction as DrugInteractionRow
from app.models.knowledge_base import Medication as MedicationRow

from .loader import KBValidationError
from .models import (
    SEVERITIES,
    CascadeRule,
    ContraindicationRule,
    DrugClass,
    Factor,
    InteractionRule,
    KnowledgeBase,
    Medication,
    product_ingredients,
)

# SRS Appendix A.2, taken from the same table the database CHECK constraints use.
# "unknown" is always allowed and is not listed here. FactorType.OTHER has no fixed
# values, so it is not part of the engine vocabulary.
RISK_FACTORS: dict[str, tuple[str, ...]] = {
    factor_type.value: tuple(v for v in values if v != "unknown")
    for factor_type, values in FACTOR_VALUES.items()
}

_SEVERITY_FROM_DB = {level.value: label for level, label in zip(Severity, SEVERITIES, strict=True)}


def load_kb_from_db(
    db: Session,
    *,
    version: str | None = None,
    updated: str | None = None,
    duplication_relevant: set[str] | None = None,
) -> KnowledgeBase:
    """Load every rule currently stored in PostgreSQL.

    Warning rule ids are the rows' ``rule_code`` (QA-EXP-04).
    Raises KBValidationError listing every problem found.
    """
    from app.core.config import settings

    version = settings.KB_VERSION if version is None else version
    updated = settings.KB_UPDATED_ON if updated is None else updated
    if duplication_relevant is None:
        duplication_relevant = settings.duplication_relevant_classes

    errors: list[str] = []
    if not version.strip():
        errors.append("kb version is required")
    try:
        date.fromisoformat(updated)
    except ValueError:
        errors.append("kb updated date must look like 2026-10-22")

    medications: dict[int, Medication] = {}
    classes: dict[str, DrugClass] = {}
    med_rows = db.scalars(
        select(MedicationRow).options(selectinload(MedicationRow.aliases)).order_by(MedicationRow.id)
    )
    for row in med_rows:
        class_name = (row.drug_class or "").strip()
        med_classes = (class_name,) if class_name else ()
        if class_name and class_name not in classes:
            classes[class_name] = DrugClass(class_name, class_name in duplication_relevant)
        medications[row.id] = Medication(
            row.id,
            row.standard_name,
            med_classes,
            tuple(alias for alias in row.alias_names if alias),
            product_ingredients(row.standard_name, (row.medication_info or {}).get("active_ingredients")),
        )

    def parse_factors(tokens: list[str] | None, where: str) -> tuple[Factor, ...]:
        factors: list[Factor] = []
        for token in tokens or []:
            name, separator, value = token.partition(":")
            name, value = name.strip(), value.strip().lower()
            if not separator or not name:
                errors.append(f"{where}: '{token}' must look like factor:value")
                continue
            if name not in RISK_FACTORS:
                errors.append(f"{where}: unknown risk factor '{name}'")
            elif value not in RISK_FACTORS[name]:
                errors.append(f"{where}: '{value}' is not an allowed value of {name}")
            else:
                factors.append((name, value))
        return tuple(factors)

    def severity_label(value: object, where: str) -> str | None:
        raw = value.value if isinstance(value, Severity) else str(value or "")
        label = _SEVERITY_FROM_DB.get(raw.lower())
        if label is None:
            errors.append(f"{where}: severity must be one of {', '.join(SEVERITIES)}")
        return label

    interactions: dict[tuple[int, int], list[InteractionRule]] = defaultdict(list)
    for row in db.scalars(select(DrugInteractionRow).order_by(DrugInteractionRow.rule_code)):
        where = f"drug_interactions {row.rule_code}"
        label = severity_label(row.severity, where)
        factors = parse_factors(list(row.relevant_risk_factors or []), where)
        if row.drug_a_id not in medications or row.drug_b_id not in medications:
            errors.append(f"{where}: medication id is not in medications")
            continue
        if row.drug_a_id == row.drug_b_id:
            errors.append(f"{where}: a medication cannot interact with itself")
            continue
        if label is None:
            continue
        low, high = sorted((row.drug_a_id, row.drug_b_id))
        interactions[(low, high)].append(
            InteractionRule(row.rule_code, low, high, label, row.description, factors, row.source)
        )

    contraindications: dict[int, list[ContraindicationRule]] = defaultdict(list)
    for row in db.scalars(select(ContraindicationRow).order_by(ContraindicationRow.rule_code)):
        where = f"contraindications {row.rule_code}"
        label = severity_label(row.severity, where)
        factor = str(getattr(row.factor_type, "value", row.factor_type) or "").strip()
        value = (row.factor_value or "").strip().lower()
        factors = parse_factors(list(row.relevant_risk_factors or []), where)
        if factor not in RISK_FACTORS:
            errors.append(f"{where}: '{factor}' is not a known risk factor")
            continue
        if value not in RISK_FACTORS[factor]:
            errors.append(f"{where}: '{value}' is not an allowed value of {factor}")
            continue
        if any(name == factor for name, _ in factors):
            errors.append(f"{where}: relevant_risk_factors must not repeat the condition factor '{factor}'")
            continue
        if row.medication_id not in medications:
            errors.append(f"{where}: medication id is not in medications")
            continue
        if label is None:
            continue
        contraindications[row.medication_id].append(
            ContraindicationRule(
                row.rule_code, row.medication_id, factor, value, label, row.description, factors, row.source
            )
        )

    cascades: list[CascadeRule] = []
    cascade_rows = db.scalars(
        select(CascadeRuleRow)
        .options(
            selectinload(CascadeRuleRow.triggering_medications),
            selectinload(CascadeRuleRow.downstream_medications),
        )
        .order_by(CascadeRuleRow.rule_code)
    )
    for row in cascade_rows:
        where = f"cascade_rules {row.rule_code}"
        # The join tables have foreign keys, so every linked medication exists. Class-based
        # patterns in the curated CSVs are expanded into medications by scripts.import_kb_rules.
        triggers = frozenset(med.id for med in row.triggering_medications)
        downstream = frozenset(med.id for med in row.downstream_medications)
        factors = parse_factors(list(row.relevant_risk_factors or []), where)
        ok = True
        if not triggers:
            errors.append(f"{where}: needs at least one triggering medication")
            ok = False
        if not downstream:
            errors.append(f"{where}: needs at least one downstream medication")
            ok = False
        if not (row.symptom_pattern or "").strip():
            errors.append(f"{where}: symptom_pattern is required")
            ok = False
        if not ok:
            continue
        cascades.append(
            CascadeRule(
                row.rule_code,
                triggers,
                frozenset(),
                row.symptom_pattern.strip(),
                downstream,
                frozenset(),
                row.description,
                factors,
                row.source,
            )
        )

    if errors:
        raise KBValidationError(errors)

    return KnowledgeBase(
        version=version,
        updated=updated,
        medications=medications,
        classes=classes,
        risk_factors=RISK_FACTORS,
        interactions={key: tuple(rules) for key, rules in interactions.items()},
        contraindications={key: tuple(rules) for key, rules in contraindications.items()},
        cascades=tuple(sorted(cascades, key=lambda rule: rule.rule_id)),
    )
