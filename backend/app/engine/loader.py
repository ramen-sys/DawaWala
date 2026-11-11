"""Load and validate the knowledge base from CSV files.

Rules are data, not code (QA-MNT-01): adding a row to a CSV adds a rule.
The loader checks every file and reports *all* problems at once, so a
curator can fix a whole batch of rows in one pass.

Files expected in the KB directory (formats in knowledge_base/README.md):
    kb_meta.json, risk_factors.csv, drug_classes.csv, medications.csv,
    interactions.csv, contraindications.csv, cascades.csv
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from .models import (
    SEVERITIES,
    UNKNOWN,
    CascadeRule,
    ContraindicationRule,
    DrugClass,
    Factor,
    InteractionRule,
    KnowledgeBase,
    Medication,
    product_ingredients,
)

# backend/app/engine/loader.py -> repo root is three levels above "engine"
DEFAULT_KB_DIR = Path(__file__).resolve().parents[3] / "knowledge_base" / "data"

COLUMNS = {
    "risk_factors.csv": ["factor", "allowed_values"],
    "drug_classes.csv": ["class_name", "duplication_relevant"],
    "medications.csv": ["medication_id", "standard_name", "classes", "aliases"],
    "interactions.csv": [
        "rule_id", "drug_a", "drug_b", "severity",
        "description", "relevant_factors", "source",
    ],
    "contraindications.csv": [
        "rule_id", "medication", "factor", "value", "severity",
        "description", "relevant_factors", "source",
    ],
    "cascades.csv": [
        "rule_id", "trigger_medications", "trigger_classes", "symptom_pattern",
        "downstream_medications", "downstream_classes",
        "description", "relevant_factors", "source",
    ],
}


class KBValidationError(Exception):
    """Raised when the knowledge-base files contain errors."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(
            f"{len(errors)} knowledge-base error(s):\n" + "\n".join(f"  - {e}" for e in errors)
        )


def _split(cell: str | None) -> list[str]:
    """Split a ';'-separated cell, ignoring blanks."""
    return [part.strip() for part in (cell or "").split(";") if part.strip()]


def _read_csv(directory: Path, filename: str, errors: list[str]) -> list[tuple[int, dict]]:
    """Read a CSV and return (line_number, row) pairs.

    utf-8-sig ignores a byte-order mark, which Windows editors often add.
    """
    path = directory / filename
    if not path.exists():
        errors.append(f"{filename}: file is missing")
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in COLUMNS[filename] if c not in (reader.fieldnames or [])]
        if missing:
            errors.append(f"{filename}: missing column(s) {', '.join(missing)}")
            return []
        rows = []
        for row in reader:
            if not any((value or "").strip() for value in row.values()):
                continue  # skip blank lines
            clean = {k: (v or "").strip() for k, v in row.items() if k is not None}
            rows.append((reader.line_num, clean))
        return rows


def load_kb(directory: str | Path = DEFAULT_KB_DIR) -> KnowledgeBase:
    """Load the knowledge base from a directory of CSV files.

    Raises KBValidationError listing every problem found.
    """
    directory = Path(directory)
    errors: list[str] = []

    # ---- metadata (SAF-07: version and last-update date) -----------------
    version, updated = "", ""
    meta_path = directory / "kb_meta.json"
    if not meta_path.exists():
        errors.append("kb_meta.json: file is missing")
    else:
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        version = str(meta.get("version", "")).strip()
        updated = str(meta.get("updated", "")).strip()
        if not version:
            errors.append("kb_meta.json: 'version' is required")
        try:
            date.fromisoformat(updated)
        except ValueError:
            errors.append("kb_meta.json: 'updated' must be a date like 2026-10-20")

    # ---- risk-factor vocabulary -------------------------------------------
    risk_factors: dict[str, tuple[str, ...]] = {}
    for line, row in _read_csv(directory, "risk_factors.csv", errors):
        where = f"risk_factors.csv line {line}"
        values = tuple(v.lower() for v in _split(row["allowed_values"]))
        if not row["factor"] or not values:
            errors.append(f"{where}: factor and allowed_values are required")
        elif UNKNOWN in values:
            errors.append(f"{where}: do not list '{UNKNOWN}'; it is always allowed")
        else:
            risk_factors[row["factor"]] = values

    def parse_factors(cell: str, where: str) -> tuple[Factor, ...]:
        factors = []
        for token in _split(cell):
            name, _, value = token.partition(":")
            name, value = name.strip(), value.strip().lower()
            if name not in risk_factors:
                errors.append(f"{where}: unknown risk factor '{name}'")
            elif value not in risk_factors[name]:
                errors.append(f"{where}: '{value}' is not an allowed value of {name}")
            else:
                factors.append((name, value))
        return tuple(factors)

    # ---- drug classes ------------------------------------------------------
    classes: dict[str, DrugClass] = {}
    for line, row in _read_csv(directory, "drug_classes.csv", errors):
        where = f"drug_classes.csv line {line}"
        flag = row["duplication_relevant"].lower()
        if flag not in ("true", "false"):
            errors.append(f"{where}: duplication_relevant must be true or false")
        elif row["class_name"] in classes:
            errors.append(f"{where}: duplicate class '{row['class_name']}'")
        else:
            classes[row["class_name"]] = DrugClass(row["class_name"], flag == "true")

    # ---- medications -------------------------------------------------------
    medications: dict[int, Medication] = {}
    by_name: dict[str, int] = {}  # standard name (lower case) -> id
    by_alias: dict[str, int] = {}  # alias (lower case) -> id
    for line, row in _read_csv(directory, "medications.csv", errors):
        where = f"medications.csv line {line}"
        try:
            med_id = int(row["medication_id"])
        except ValueError:
            errors.append(f"{where}: medication_id must be a whole number")
            continue
        name = row["standard_name"]
        med_classes = tuple(_split(row["classes"]))
        aliases = tuple(_split(row["aliases"]))
        if med_id in medications:
            errors.append(f"{where}: medication_id {med_id} is used twice")
            continue
        if not name:
            errors.append(f"{where}: standard_name is required")
            continue
        if name.lower() in by_name:
            errors.append(f"{where}: standard name '{name}' is used twice")
            continue
        for cls in med_classes:
            if cls not in classes:
                errors.append(f"{where}: class '{cls}' is not in drug_classes.csv")
        medications[med_id] = Medication(med_id, name, med_classes, aliases, product_ingredients(name, None))
        by_name[name.lower()] = med_id

    # Aliases must point to exactly one medication, and must not clash with
    # another medication's standard name, or normalization becomes ambiguous.
    for med in medications.values():
        for alias in med.aliases:
            key = alias.lower()
            if key in by_name and by_name[key] != med.medication_id:
                errors.append(
                    f"medications.csv: alias '{alias}' of {med.standard_name} "
                    f"is the standard name of another medication"
                )
            elif key in by_alias and by_alias[key] != med.medication_id:
                other = medications[by_alias[key]].standard_name
                errors.append(
                    f"medications.csv: alias '{alias}' is used by both "
                    f"{other} and {med.standard_name}"
                )
            else:
                by_alias[key] = med.medication_id

    def resolve(cell: str, where: str) -> int | None:
        """Rule files refer to medications by standard name only."""
        key = cell.strip().lower()
        if key in by_name:
            return by_name[key]
        if key in by_alias:
            real = medications[by_alias[key]].standard_name
            errors.append(f"{where}: '{cell}' is a brand/alias; use the standard name '{real}'")
        else:
            errors.append(f"{where}: unknown medication '{cell}'")
        return None

    seen_rule_ids: set[str] = set()

    def check_rule_id(rule_id: str, where: str) -> bool:
        if not rule_id:
            errors.append(f"{where}: rule_id is required")
            return False
        if rule_id in seen_rule_ids:
            errors.append(f"{where}: rule_id {rule_id} is used twice")
            return False
        seen_rule_ids.add(rule_id)
        return True

    def check_severity(severity: str, where: str) -> bool:
        if severity not in SEVERITIES:
            errors.append(f"{where}: severity must be one of {', '.join(SEVERITIES)}")
            return False
        return True

    # ---- interactions (FR-8) ----------------------------------------------
    interactions: dict[tuple[int, int], list[InteractionRule]] = defaultdict(list)
    for line, row in _read_csv(directory, "interactions.csv", errors):
        where = f"interactions.csv line {line}"
        ok = check_rule_id(row["rule_id"], where)
        a = resolve(row["drug_a"], where)
        b = resolve(row["drug_b"], where)
        ok = check_severity(row["severity"], where) and ok
        factors = parse_factors(row["relevant_factors"], where)
        if a is not None and a == b:
            errors.append(f"{where}: a medication cannot interact with itself")
            continue
        if not ok or a is None or b is None:
            continue
        low, high = sorted((a, b))
        interactions[(low, high)].append(
            InteractionRule(row["rule_id"], low, high, row["severity"],
                            row["description"], factors, row["source"])
        )

    # ---- contraindications (FR-10) ----------------------------------------
    contraindications: dict[int, list[ContraindicationRule]] = defaultdict(list)
    for line, row in _read_csv(directory, "contraindications.csv", errors):
        where = f"contraindications.csv line {line}"
        ok = check_rule_id(row["rule_id"], where)
        med_id = resolve(row["medication"], where)
        ok = check_severity(row["severity"], where) and ok
        factor, value = row["factor"], row["value"].lower()
        if factor not in risk_factors:
            errors.append(f"{where}: unknown risk factor '{factor}'")
            continue
        if value not in risk_factors[factor]:
            errors.append(f"{where}: '{value}' is not an allowed value of {factor}")
            continue
        extra = parse_factors(row["relevant_factors"], where)
        if (factor, value) in extra:
            # The condition already triggers the warning; listing it again
            # would let scoring count the same factor twice (SRS Table 5.2).
            errors.append(f"{where}: relevant_factors must not repeat the condition {factor}:{value}")
            continue
        if not ok or med_id is None:
            continue
        contraindications[med_id].append(
            ContraindicationRule(row["rule_id"], med_id, factor, value, row["severity"],
                                 row["description"], extra, row["source"])
        )

    # ---- prescribing cascades (FR-12) -------------------------------------
    cascades: list[CascadeRule] = []
    for line, row in _read_csv(directory, "cascades.csv", errors):
        where = f"cascades.csv line {line}"
        ok = check_rule_id(row["rule_id"], where)
        sides = {}
        for side in ("trigger", "downstream"):
            meds = [resolve(n, where) for n in _split(row[f"{side}_medications"])]
            cls = _split(row[f"{side}_classes"])
            for c in cls:
                if c not in classes:
                    errors.append(f"{where}: class '{c}' is not in drug_classes.csv")
                    ok = False
            if not meds and not cls:
                errors.append(f"{where}: needs at least one {side} medication or class")
                ok = False
            if None in meds:
                ok = False
            sides[side] = (frozenset(m for m in meds if m is not None), frozenset(cls))
        if not row["symptom_pattern"]:
            errors.append(f"{where}: symptom_pattern is required")
            ok = False
        factors = parse_factors(row["relevant_factors"], where)
        if not ok:
            continue
        cascades.append(
            CascadeRule(row["rule_id"], sides["trigger"][0], sides["trigger"][1],
                        row["symptom_pattern"], sides["downstream"][0], sides["downstream"][1],
                        row["description"], factors, row["source"])
        )

    if errors:
        raise KBValidationError(errors)

    return KnowledgeBase(
        version=version,
        updated=updated,
        medications=medications,
        classes=classes,
        risk_factors=risk_factors,
        interactions={k: tuple(v) for k, v in interactions.items()},
        contraindications={k: tuple(v) for k, v in contraindications.items()},
        cascades=tuple(sorted(cascades, key=lambda r: r.rule_id)),
    )
