"""analyze(): input handling, ordering and output shape."""

import json
import random

import pytest

from app.engine import ConfirmedItem, analyze


def test_unrecognised_items_are_listed_not_dropped(kb, items):
    result = analyze(items("warfarin", "?Xyzmed 500"), kb)
    [n] = result.not_analysed
    assert (n.entered_text, n.reason) == ("Xyzmed 500", "unrecognised")


def test_medication_id_missing_from_kb_is_listed(kb):
    result = analyze([ConfirmedItem("a", 9999, "Oldmed")], kb)
    [n] = result.not_analysed
    assert n.reason == "not_in_knowledge_base"
    assert result.warnings == []


def test_result_is_identical_regardless_of_input_order(kb, items):
    """QA-REL-01: same list + factors + KB version -> identical output."""
    names = ["warfarin", "aspirin", "ibuprofen", "naproxen", "lisinopril", "amlodipine",
             "furosemide", "metformin", "Panadol", "Calpol", "?Unknownium"]
    factors = {"age_range": "65_plus"}

    def run(order):
        data = analyze(items(*order), kb, factors).to_dict()
        # item ids follow entry order, so compare everything except them
        for n in data["not_analysed"]:
            n.pop("item_id")
        return data

    expected = run(names)
    for seed in range(20):
        shuffled = names[:]
        random.Random(seed).shuffle(shuffled)
        assert run(shuffled) == expected


def test_warnings_are_grouped_in_category_order(kb, items):
    meds = items("metformin", "warfarin", "aspirin", "amlodipine", "furosemide", "Panadol", "Calpol")
    result = analyze(meds, kb, {"kidney_function": "impaired"})
    categories = [w.category for w in result.warnings]
    order = ["contraindication", "DDI", "cascade", "duplicate"]
    assert categories == sorted(categories, key=order.index)
    assert set(categories) == set(order)


def test_output_is_json_serialisable(kb, items):
    result = analyze(items("warfarin", "aspirin", "?Foo"), kb)
    data = json.loads(json.dumps(result.to_dict()))
    assert data["kb_version"] == kb.version
    assert data["kb_updated"] == kb.updated
    assert data["warnings"][0]["rule_id"] == "INT-0001"


def test_unknown_risk_factor_is_rejected(kb, items):
    with pytest.raises(ValueError, match="Unknown risk factor"):
        analyze(items("warfarin"), kb, {"blood_group": "A"})


def test_invalid_risk_factor_value_is_rejected(kb, items):
    with pytest.raises(ValueError, match="Invalid value"):
        analyze(items("warfarin"), kb, {"kidney_function": "bad"})


def test_risk_factor_values_are_case_insensitive(kb, items):
    result = analyze(items("metformin"), kb, {"kidney_function": " Impaired "})
    assert [w.rule_id for w in result.warnings] == ["CI-0001"]


def test_none_value_counts_as_unknown(kb, items):
    result = analyze(items("metformin"), kb, {"kidney_function": None})
    assert [n.rule_id for n in result.not_assessed] == ["CI-0001"]
