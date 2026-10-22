"""FR-12: prescribing-cascade detection."""

from app.engine import analyze
from tests.conftest import by_rule


def test_trigger_and_downstream_present(kb, items):
    [w] = by_rule(analyze(items("amlodipine", "furosemide"), kb), "CAS-0001")
    assert w.category == "cascade"
    assert w.details["trigger_names"] == ["amlodipine"]
    assert w.details["downstream_names"] == ["furosemide"]
    assert "swelling" in w.details["symptom_pattern"]
    assert w.severity is None


def test_only_one_side_present_gives_nothing(kb, items):
    assert not by_rule(analyze(items("amlodipine"), kb), "CAS-0001")
    assert not by_rule(analyze(items("furosemide"), kb), "CAS-0001")


def test_rule_by_medication_name(kb, items):
    [w] = by_rule(analyze(items("Maxolon", "Sinemet"), kb), "CAS-0003")
    assert w.details["trigger_names"] == ["metoclopramide"]


def test_several_triggers_and_downstreams_make_one_warning(kb, items):
    meds = items("ibuprofen", "naproxen", "lisinopril", "amlodipine")
    [w] = by_rule(analyze(meds, kb), "CAS-0004")
    assert set(w.details["trigger_names"]) == {"ibuprofen", "naproxen"}
    assert set(w.details["downstream_names"]) == {"lisinopril", "amlodipine"}


def test_relevant_factor_is_matched(kb, items):
    [w] = by_rule(analyze(items("donepezil", "oxybutynin"), kb, {"age_range": "65_plus"}), "CAS-0002")
    assert w.matched_factors == ("age_range:65_plus",)


def test_medicine_that_is_both_trigger_and_downstream_alone_is_no_cascade(kb):
    # A rule whose trigger and downstream patterns both cover the same single
    # medicine must not match on that medicine alone.
    from app.engine.cascades import _match
    from app.engine.models import CascadeRule

    rule = CascadeRule("CAS-T", frozenset({8}), frozenset(), "x", frozenset({8}),
                       frozenset(), "", (), "")
    assert _match(rule, [8], kb) is None
    assert _match(rule, [8, 10], kb) is None  # 10 is in neither side
