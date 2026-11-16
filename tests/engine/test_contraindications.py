"""FR-10: contraindication detection and the "Not assessed" list."""

from app.engine import analyze
from tests.conftest import by_rule


def test_matching_factor_raises_warning(kb, items):
    result = analyze(items("metformin"), kb, {"kidney_function": "impaired"})
    [w] = by_rule(result, "CI-0001")
    assert w.category == "contraindication"
    assert w.severity == "Contraindicated"
    assert w.details == {"condition": "kidney_function:impaired"}
    assert result.not_assessed == []


def test_unknown_factor_goes_to_not_assessed(kb, items):
    result = analyze(items("metformin"), kb)  # nothing supplied
    assert not by_rule(result, "CI-0001")
    [n] = result.not_assessed
    assert (n.rule_id, n.medication_name, n.missing_factor) == ("CI-0001", "metformin", "kidney_function")


def test_explicit_unknown_is_treated_like_missing(kb, items):
    result = analyze(items("metformin"), kb, {"kidney_function": "Unknown"})
    assert [n.rule_id for n in result.not_assessed] == ["CI-0001"]


def test_known_factor_that_does_not_match_gives_nothing(kb, items):
    result = analyze(items("metformin"), kb, {"kidney_function": "normal"})
    assert not by_rule(result, "CI-0001")
    assert result.not_assessed == []


def test_extra_relevant_factors_are_reported(kb, items):
    factors = {"kidney_function": "impaired", "age_range": "65_plus"}
    [w] = by_rule(analyze(items("ibuprofen"), kb, factors), "CI-0002")
    assert w.matched_factors == ("age_range:65_plus",)


def test_age_based_contraindication(kb, items):
    assert by_rule(analyze(items("metoclopramide"), kb, {"age_range": "under_18"}), "CI-0008")
    assert not by_rule(analyze(items("metoclopramide"), kb, {"age_range": "18_64"}), "CI-0008")


def test_duplicate_entries_do_not_duplicate_warnings(kb, items):
    result = analyze(items("Glucophage", "metformin"), kb, {"kidney_function": "impaired"})
    assert len(by_rule(result, "CI-0001")) == 1
