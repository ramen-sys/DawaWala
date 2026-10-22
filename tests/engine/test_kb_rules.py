"""QA-COR-03: at least one automated test for every rule in the knowledge base.

These tests are generated from knowledge_base/data, so every row a curator
adds is tested automatically - no test needs to be written by hand.
"""

import pytest

from app.engine import ConfirmedItem, analyze, load_kb
from app.engine.loader import DEFAULT_KB_DIR

KB = load_kb(DEFAULT_KB_DIR)
INTERACTIONS = [r for rules in KB.interactions.values() for r in rules]
CONTRAINDICATIONS = [r for rules in KB.contraindications.values() for r in rules]


def confirmed(*med_ids):
    return [ConfirmedItem(i, m, KB.name(m)) for i, m in enumerate(med_ids)]


def first_member(meds, classes):
    """Pick a real medication matching one side of a cascade rule."""
    if meds:
        return min(meds)
    return min(m.medication_id for m in KB.medications.values() if classes.intersection(m.classes))


@pytest.mark.parametrize("rule", INTERACTIONS, ids=lambda r: r.rule_id)
def test_interaction_rule_fires(rule):
    result = analyze(confirmed(rule.drug_a, rule.drug_b), KB)
    assert rule.rule_id in {w.rule_id for w in result.warnings}


@pytest.mark.parametrize("rule", CONTRAINDICATIONS, ids=lambda r: r.rule_id)
def test_contraindication_rule_fires_and_is_reported_when_unknown(rule):
    hit = analyze(confirmed(rule.medication_id), KB, {rule.factor: rule.value})
    assert rule.rule_id in {w.rule_id for w in hit.warnings}

    unknown = analyze(confirmed(rule.medication_id), KB)
    assert rule.rule_id in {n.rule_id for n in unknown.not_assessed}


@pytest.mark.parametrize("rule", KB.cascades, ids=lambda r: r.rule_id)
def test_cascade_rule_fires(rule):
    trigger = first_member(rule.trigger_medications, rule.trigger_classes)
    downstream = first_member(rule.downstream_medications, rule.downstream_classes)
    result = analyze(confirmed(trigger, downstream), KB)
    assert rule.rule_id in {w.rule_id for w in result.warnings}
