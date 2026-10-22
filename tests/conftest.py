from pathlib import Path

import pytest

from app.engine import ConfirmedItem, load_kb
from app.engine.loader import DEFAULT_KB_DIR

FIXTURE_KB = Path(__file__).parent / "engine" / "fixtures" / "kb"


@pytest.fixture(scope="session")
def kb():
    """Frozen test knowledge base (QA-TST-02). Change it only on purpose."""
    return load_kb(FIXTURE_KB)


@pytest.fixture(scope="session")
def real_kb():
    """The knowledge base being curated in knowledge_base/data."""
    return load_kb(DEFAULT_KB_DIR)


@pytest.fixture
def items(kb):
    """Build a confirmed list from names as a user might enter them.

    items("Panadol", "warfarin") -> ConfirmedItems with resolved ids.
    A name prefixed with "?" is kept as unrecognised (medication_id None).
    """
    lookup = {}
    for med in kb.medications.values():
        lookup[med.standard_name.lower()] = med.medication_id
        for alias in med.aliases:
            lookup[alias.lower()] = med.medication_id

    def build(*names):
        result = []
        for i, name in enumerate(names, start=1):
            if name.startswith("?"):
                result.append(ConfirmedItem(i, None, name[1:]))
            else:
                result.append(ConfirmedItem(i, lookup[name.lower()], name))
        return result

    return build


def by_rule(result_or_warnings, rule_id):
    warnings = getattr(result_or_warnings, "warnings", result_or_warnings)
    return [w for w in warnings if w.rule_id == rule_id]
