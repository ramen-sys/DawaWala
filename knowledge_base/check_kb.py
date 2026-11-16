"""Validate the knowledge base in PostgreSQL and show progress towards the release targets.

Run from the repository root:
    python knowledge_base/check_kb.py

Exits with code 1 if any rule is invalid, so it can also run in CI.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.engine.db_loader import load_kb_from_db  # noqa: E402
from app.engine.loader import KBValidationError  # noqa: E402

# Release 1.0 minimums (SRS QA-COR-04 / Section 2.7)
TARGETS = {"medications": 300, "interactions": 1000, "contraindications": 100, "cascade rules": 20}


def main() -> int:
    try:
        with SessionLocal() as db:
            kb = load_kb_from_db(db)
    except KBValidationError as exc:
        print(exc)
        return 1

    counts = {
        "medications": len(kb.medications),
        "interactions": sum(len(rules) for rules in kb.interactions.values()),
        "contraindications": sum(len(rules) for rules in kb.contraindications.values()),
        "cascade rules": len(kb.cascades),
    }
    print(f"Knowledge base {kb.version} (updated {kb.updated}) is valid.\n")
    print(f"{'':20}{'have':>8}{'target':>8}")
    for name, have in counts.items():
        mark = "ok" if have >= TARGETS[name] else f"{have / TARGETS[name]:.0%}"
        print(f"{name:20}{have:>8}{TARGETS[name]:>8}   {mark}")
    generated = sum(1 for rules in kb.interactions.values() for rule in rules if rule.parent_rule_id)
    if generated:
        print(f"\n{generated} of the interactions come from class-level rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
