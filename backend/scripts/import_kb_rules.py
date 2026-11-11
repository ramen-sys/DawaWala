"""Import the curated safety rules (FR-8, FR-10, FR-12) into the knowledge-base tables.

Source files (knowledge_base/data/): medications.csv, drug_classes.csv, interactions.csv,
contraindications.csv, cascades.csv. They are validated with the engine's CSV loader first,
so a bad row stops the import before anything is written.

Run from backend/, AFTER scripts.import_medicines (that script replaces the aliases of the
Kaggle medications, which removes extra brand names added here):

    python -m scripts.import_medicines
    python -m scripts.import_kb_rules [--dry-run]

What it does:
* Medications: curated medicines missing from the database are added. Existing ones keep their
  Kaggle class and source; only missing brand names are added as aliases.
* Interactions, contraindications, cascades: upserted by rule_code. Rules removed from the CSVs
  are deleted (contraindications imported from the Kaggle dataset are never touched).
* Cascade rules written against a drug class are expanded into every medication of that class
  currently in the database. Re-run this script after adding medications to such a class.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.engine.loader import DEFAULT_KB_DIR, KBValidationError, load_kb
from app.engine.models import KnowledgeBase, format_factors
from app.models import CascadeRule, Contraindication, DrugInteraction, Medication, MedicationAlias
from app.models.enums import FactorType, Severity
from scripts.import_medicines import SOURCE as KAGGLE_SOURCE

# Source recorded on medications that only exist because a curated rule needs them (SRS 5.3).
CURATED_MEDICATION_SOURCE = "Curated knowledge base (knowledge_base/data/medications.csv)"


class CuratedImportError(Exception):
    """The curated data cannot be imported as it stands; .errors lists every problem."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Cannot import curated rules:\n  - " + "\n  - ".join(errors))


def load_curated(directory: str | Path = DEFAULT_KB_DIR) -> KnowledgeBase:
    """Validate and load the curated CSVs (raises KBValidationError)."""
    return load_kb(directory)


def check_curated(kb: KnowledgeBase, duplication_relevant: set[str]) -> list[str]:
    """Problems that the CSV loader allows but the database schema or config cannot represent."""
    errors = []
    for cls in sorted(kb.classes.values(), key=lambda c: c.name):
        if cls.duplication_relevant != (cls.name in duplication_relevant):
            errors.append(
                f"drug_classes.csv: '{cls.name}' duplication_relevant={str(cls.duplication_relevant).lower()} "
                f"disagrees with DUPLICATION_RELEVANT_CLASSES in app/core/config.py"
            )
    for med in sorted(kb.medications.values(), key=lambda m: m.standard_name):
        if len(med.classes) > 1:
            errors.append(f"medications.csv: {med.standard_name} has {len(med.classes)} classes; "
                          "the database stores one drug_class per medication")
    pairs = Counter((rule.drug_a, rule.drug_b) for rules in kb.interactions.values() for rule in rules)
    for (a, b), count in sorted(pairs.items()):
        if count > 1:
            errors.append(f"interactions.csv: {kb.name(a)} + {kb.name(b)} has {count} rules; "
                          "the database allows one rule per pair")
    return errors


def _upsert(db: Session, model, rows: list[dict], update: list[str]) -> None:
    if not rows:
        return
    stmt = insert(model).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[model.rule_code], set_={col: stmt.excluded[col] for col in update}
    )
    db.execute(stmt)


def import_rules(db: Session, kb: KnowledgeBase, duplication_relevant: set[str] | None = None) -> dict[str, int]:
    """Write the curated KB into the database. Does not commit; the caller does.

    Returns counts per table. Raises CuratedImportError listing every problem found.
    """
    if duplication_relevant is None:
        duplication_relevant = settings.duplication_relevant_classes
    errors = check_curated(kb, duplication_relevant)
    # The version stamped on every analysis comes from settings, so the files must agree (SAF-07).
    if (kb.version, kb.updated) != (settings.KB_VERSION, settings.KB_UPDATED_ON):
        errors.append(f"kb_meta.json says {kb.version} ({kb.updated}) but app/core/config.py says "
                      f"{settings.KB_VERSION} ({settings.KB_UPDATED_ON}); update both together")
    if errors:
        raise CuratedImportError(errors)

    notes: list[str] = []

    # 1. Medications and aliases --------------------------------------------------------
    existing = {
        row.standard_name.lower(): row
        for row in db.scalars(select(Medication).options(selectinload(Medication.aliases)))
    }
    added = 0
    for med in kb.medications.values():
        drug_class = med.classes[0] if med.classes else None
        row = existing.get(med.standard_name.lower())
        if row is None:
            row = Medication(standard_name=med.standard_name, drug_class=drug_class,
                             medication_info={}, source=CURATED_MEDICATION_SOURCE)
            db.add(row)
            existing[med.standard_name.lower()] = row
            added += 1
        elif (row.drug_class or None) != drug_class:
            notes.append(f"{row.standard_name}: database class '{row.drug_class}' kept "
                         f"(medications.csv says '{drug_class}')")
    db.flush()

    db_id = {med.medication_id: existing[med.standard_name.lower()].id for med in kb.medications.values()}
    alias_rows = [
        {"medication_id": db_id[med.medication_id], "alias": alias}
        for med in kb.medications.values()
        for alias in med.aliases
    ]
    if alias_rows:
        db.execute(insert(MedicationAlias).values(alias_rows).on_conflict_do_nothing(
            constraint="uq_medication_aliases_med_alias"))

    # 2. Interactions (FR-8) --------------------------------------------------------------
    interactions = [rule for rules in kb.interactions.values() for rule in rules]
    codes = [rule.rule_id for rule in interactions]
    db.execute(delete(DrugInteraction).where(DrugInteraction.rule_code.not_in(codes)))
    rows = []
    for rule in interactions:
        low, high = sorted((db_id[rule.drug_a], db_id[rule.drug_b]))
        rows.append({
            "rule_code": rule.rule_id, "drug_a_id": low, "drug_b_id": high,
            "description": rule.description, "severity": Severity(rule.severity.lower()),
            "relevant_risk_factors": list(format_factors(rule.relevant_factors)), "source": rule.source,
        })
    _upsert(db, DrugInteraction, rows,
            ["drug_a_id", "drug_b_id", "description", "severity", "relevant_risk_factors", "source"])

    # 3. Contraindications (FR-10) --------------------------------------------------------
    contraindications = [rule for rules in kb.contraindications.values() for rule in rules]
    codes = [rule.rule_id for rule in contraindications]
    # Kaggle age rules belong to scripts.import_medicines and are never deleted here.
    db.execute(delete(Contraindication).where(
        Contraindication.rule_code.not_in(codes),
        Contraindication.source != KAGGLE_SOURCE,
    ))
    taken = {
        (row.medication_id, str(row.factor_type), row.factor_value): row.rule_code
        for row in db.scalars(select(Contraindication))
    }
    rows = []
    for rule in contraindications:
        key = (db_id[rule.medication_id], rule.factor, rule.value)
        if taken.get(key, rule.rule_id) != rule.rule_id:
            errors.append(f"contraindications.csv {rule.rule_id}: {kb.name(rule.medication_id)} already has "
                          f"rule {taken[key]} for {rule.factor}:{rule.value}")
            continue
        rows.append({
            "rule_code": rule.rule_id, "medication_id": key[0], "factor_type": FactorType(rule.factor),
            "factor_value": rule.value, "description": rule.description,
            "severity": Severity(rule.severity.lower()),
            "relevant_risk_factors": list(format_factors(rule.relevant_factors)), "source": rule.source,
        })
    if errors:
        raise CuratedImportError(errors)
    _upsert(db, Contraindication, rows,
            ["medication_id", "factor_type", "factor_value", "description", "severity",
             "relevant_risk_factors", "source"])

    # 4. Cascades (FR-12): classes expanded to the medications currently in the database --
    by_class: dict[str, list[Medication]] = {}
    for row in sorted(existing.values(), key=lambda m: m.id):
        by_class.setdefault(row.drug_class, []).append(row)
    by_db_id = {row.id: row for row in existing.values()}

    def members(med_ids, classes) -> list[Medication]:
        found = {db_id[m] for m in med_ids}
        for cls in classes:
            found.update(row.id for row in by_class.get(cls, []))
        return [by_db_id[i] for i in sorted(found)]

    db.execute(delete(CascadeRule).where(CascadeRule.rule_code.not_in([r.rule_id for r in kb.cascades])))
    current = {row.rule_code: row for row in db.scalars(select(CascadeRule))}
    for rule in kb.cascades:
        row = current.get(rule.rule_id) or CascadeRule(rule_code=rule.rule_id)
        row.symptom_pattern = rule.symptom_pattern
        row.description = rule.description
        row.relevant_risk_factors = list(format_factors(rule.relevant_factors))
        row.source = rule.source
        row.triggering_medications = members(rule.trigger_medications, rule.trigger_classes)
        row.downstream_medications = members(rule.downstream_medications, rule.downstream_classes)
        db.add(row)
    db.flush()

    for note in notes:
        print(f"  note: {note}")
    return {
        "medications added": added,
        "interactions": len(interactions),
        "contraindications": len(contraindications),
        "cascade rules": len(kb.cascades),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=str(DEFAULT_KB_DIR), help="folder with the curated CSVs")
    parser.add_argument("--dry-run", action="store_true", help="validate and roll back instead of committing")
    args = parser.parse_args(argv)

    try:
        kb = load_curated(args.data_dir)
        with SessionLocal() as db:
            counts = import_rules(db, kb)
            if args.dry_run:
                db.rollback()
            else:
                db.commit()
    except (KBValidationError, CuratedImportError) as exc:
        print(exc)
        return 1

    verb = "Would import" if args.dry_run else "Imported"
    print(f"{verb} curated knowledge base {kb.version}: "
          + ", ".join(f"{n} {name}" for name, n in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
