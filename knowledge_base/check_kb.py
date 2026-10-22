"""Validate the knowledge base and show progress towards the release targets.

Run from the repository root:
    python knowledge_base/check_kb.py              # checks knowledge_base/data
    python knowledge_base/check_kb.py path/to/kb   # checks another folder

Exits with code 1 if any file has errors, so it can also run in CI.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.loader import DEFAULT_KB_DIR, KBValidationError, load_kb  # noqa: E402

# Release 1.0 minimums (SRS QA-COR-04 / Section 2.7)
TARGETS = {"medications": 300, "interactions": 1000, "contraindications": 100, "cascade rules": 20}


def main() -> int:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_KB_DIR
    try:
        kb = load_kb(directory)
    except KBValidationError as exc:
        print(exc)
        return 1

    counts = {
        "medications": len(kb.medications),
        "interactions": sum(len(r) for r in kb.interactions.values()),
        "contraindications": sum(len(r) for r in kb.contraindications.values()),
        "cascade rules": len(kb.cascades),
    }
    print(f"Knowledge base {kb.version} (updated {kb.updated}) is valid.\n")
    print(f"{'':20}{'have':>8}{'target':>8}")
    for name, have in counts.items():
        mark = "ok" if have >= TARGETS[name] else f"{have / TARGETS[name]:.0%}"
        print(f"{name:20}{have:>8}{TARGETS[name]:>8}   {mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
