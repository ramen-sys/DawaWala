"""Build or refresh the clinical review sheet for the curated rules (SAF-09).

Run from the repository root:
    python knowledge_base/review_sheet.py            # write review/clinical_review.csv
    python knowledge_base/review_sheet.py --check    # only report review status; exit 1 if not all approved

One row per curated rule (interactions, contraindications, cascades). The rule
columns are regenerated from the CSVs every time; the reviewer columns
(reviewer_name ... reviewer_comments) are kept. If a rule changes after it was
reviewed, its decision is reset to blank so it is reviewed again: the sheet
stores a fingerprint of the rule content that was approved.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.loader import DEFAULT_KB_DIR, load_kb  # noqa: E402
from app.engine.models import format_factors  # noqa: E402

SHEET = Path(__file__).resolve().parent / "review" / "clinical_review.csv"
EVIDENCE = Path(__file__).resolve().parent / "review" / "evidence_check.csv"

RULE_COLUMNS = ["rule_id", "type", "rule", "severity", "relevant_factors", "description", "source",
                "evidence_check", "fingerprint"]
REVIEW_COLUMNS = ["reviewer_name", "reviewer_role", "review_date", "decision", "reviewer_comments"]
DECISIONS = {"approved", "changes_needed", "rejected"}


def rules(kb) -> list[dict]:
    rows = []
    for rule in sorted((r for rs in kb.interactions.values() for r in rs), key=lambda r: r.rule_id):
        rows.append({"rule_id": rule.rule_id, "type": "interaction",
                     "rule": f"{kb.name(rule.drug_a)} + {kb.name(rule.drug_b)}",
                     "severity": rule.severity, "factors": rule.relevant_factors,
                     "description": rule.description, "source": rule.source})
    for rule in sorted((r for rs in kb.contraindications.values() for r in rs), key=lambda r: r.rule_id):
        rows.append({"rule_id": rule.rule_id, "type": "contraindication",
                     "rule": f"{kb.name(rule.medication_id)} when {rule.factor} = {rule.value}",
                     "severity": rule.severity, "factors": rule.relevant_factors,
                     "description": rule.description, "source": rule.source})
    for rule in kb.cascades:
        trigger = sorted(kb.names(tuple(rule.trigger_medications))) + sorted(rule.trigger_classes)
        downstream = sorted(kb.names(tuple(rule.downstream_medications))) + sorted(rule.downstream_classes)
        rows.append({"rule_id": rule.rule_id, "type": "cascade",
                     "rule": f"{' / '.join(trigger)} -> {rule.symptom_pattern} -> {' / '.join(downstream)}",
                     "severity": "", "factors": rule.relevant_factors,
                     "description": rule.description, "source": rule.source})
    for row in rows:
        row["relevant_factors"] = ";".join(format_factors(row.pop("factors")))
        content = "|".join(row[k] for k in ("rule", "severity", "relevant_factors", "description", "source"))
        row["fingerprint"] = hashlib.sha256(content.encode()).hexdigest()[:12]
    return rows


def read_csv(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["rule_id"]: row for row in csv.DictReader(f)}


def build(directory: Path | None = None) -> list[dict]:
    old = read_csv(SHEET)
    evidence = read_csv(EVIDENCE)
    sheet = []
    for row in rules(load_kb(directory or DEFAULT_KB_DIR)):
        row["evidence_check"] = evidence.get(row["rule_id"], {}).get("summary", "")
        previous = old.get(row["rule_id"], {})
        for col in REVIEW_COLUMNS:
            row[col] = previous.get(col, "")
        if previous and previous.get("fingerprint") != row["fingerprint"] and row["decision"]:
            row["reviewer_comments"] = (f"[rule changed after review; previous decision: {row['decision']}] "
                                        + row["reviewer_comments"]).strip()
            row["decision"] = ""
        sheet.append(row)
    return sheet


def status(sheet: list[dict]) -> tuple[int, list[str]]:
    problems = []
    approved = 0
    for row in sheet:
        decision = row["decision"].strip().lower()
        if decision and decision not in DECISIONS:
            problems.append(f"{row['rule_id']}: decision '{row['decision']}' must be one of {sorted(DECISIONS)}")
        elif decision == "approved":
            if not (row["reviewer_name"].strip() and row["reviewer_role"].strip() and row["review_date"].strip()):
                problems.append(f"{row['rule_id']}: approved without reviewer name, role and date")
            else:
                approved += 1
    return approved, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report status only, do not write")
    args = parser.parse_args(argv)

    sheet = build()
    if not args.check:
        SHEET.parent.mkdir(exist_ok=True)
        with SHEET.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=RULE_COLUMNS + REVIEW_COLUMNS)
            writer.writeheader()
            writer.writerows(sheet)
        print(f"Wrote {SHEET.relative_to(ROOT)} ({len(sheet)} rules)")

    approved, problems = status(sheet)
    for problem in problems:
        print(f"  problem: {problem}")
    print(f"Clinically approved: {approved}/{len(sheet)} rules (SAF-09)")
    return 0 if approved == len(sheet) and not problems else 1


if __name__ == "__main__":
    sys.exit(main())
