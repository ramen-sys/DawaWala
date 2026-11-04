"""QA-COR-03: at least one automated test for every rule stored in the database.

Rules come from PostgreSQL, so a row added there is tested without a new
hand-written test.
"""

import pytest

from app.db.session import SessionLocal
from app.engine import ConfirmedItem, analyze, load_kb_from_db

with SessionLocal() as _db:
    KB = load_kb_from_db(_db)

INTERACTIONS = [rule for rules in KB.interactions.values() for rule in rules]
CONTRAINDICATIONS = [rule for rules in KB.contraindications.values() for rule in rules]


def confirmed(*med_ids):
    return [ConfirmedItem(i, med_id, KB.name(med_id)) for i, med_id in enumerate(med_ids)]


def first_member(meds, classes):
    """Pick a real medication matching one side of a cascade rule."""
    if meds:
        return min(meds)
    return min(med.medication_id for med in KB.medications.values() if classes.intersection(med.classes))


if INTERACTIONS:

    @pytest.mark.parametrize("rule", INTERACTIONS, ids=lambda rule: rule.rule_id)
    def test_interaction_rule_fires(rule):
        result = analyze(confirmed(rule.drug_a, rule.drug_b), KB)
        assert rule.rule_id in {warning.rule_id for warning in result.warnings}

else:

    def test_interaction_rule_fires():
        pytest.skip("no interaction rules in the database")


if CONTRAINDICATIONS:

    @pytest.mark.parametrize("rule", CONTRAINDICATIONS, ids=lambda rule: rule.rule_id)
    def test_contraindication_rule_fires_and_is_reported_when_unknown(rule):
        hit = analyze(confirmed(rule.medication_id), KB, {rule.factor: rule.value})
        assert rule.rule_id in {warning.rule_id for warning in hit.warnings}

        unknown = analyze(confirmed(rule.medication_id), KB)
        assert rule.rule_id in {item.rule_id for item in unknown.not_assessed}

else:

    def test_contraindication_rule_fires_and_is_reported_when_unknown():
        pytest.skip("no contraindication rules in the database")


if KB.cascades:

    @pytest.mark.parametrize("rule", KB.cascades, ids=lambda rule: rule.rule_id)
    def test_cascade_rule_fires(rule):
        trigger = first_member(rule.trigger_medications, rule.trigger_classes)
        downstream = first_member(rule.downstream_medications, rule.downstream_classes)
        result = analyze(confirmed(trigger, downstream), KB)
        assert rule.rule_id in {warning.rule_id for warning in result.warnings}

else:

    def test_cascade_rule_fires():
        pytest.skip("no cascade rules in the database")
