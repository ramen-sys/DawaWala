"""FR-8: drug-drug interaction detection."""

from app.engine import analyze
from tests.conftest import by_rule


def test_known_pair_is_reported(kb, items):
    result = analyze(items("warfarin", "aspirin"), kb)
    [w] = by_rule(result, "INT-0001")
    assert w.category == "DDI"
    assert w.severity == "Major"
    assert set(w.medication_names) == {"warfarin", "aspirin"}
    assert w.kb_version == kb.version


def test_order_of_entry_does_not_matter(kb, items):
    first = analyze(items("aspirin", "warfarin"), kb).warnings
    second = analyze(items("warfarin", "aspirin"), kb).warnings
    assert [w.to_dict() for w in first] == [w.to_dict() for w in second]


def test_brand_names_are_checked_as_their_standard_medicine(kb, items):
    # Disprin is aspirin, Coumadin is warfarin.
    assert by_rule(analyze(items("Disprin", "Coumadin"), kb), "INT-0001")


def test_pair_without_record_gives_no_interaction(kb, items):
    result = analyze(items("paracetamol", "metformin"), kb)
    assert not [w for w in result.warnings if w.category == "DDI"]


def test_single_medicine_and_empty_list(kb, items):
    assert analyze(items("warfarin"), kb).warnings == []
    assert analyze([], kb).warnings == []


def test_same_medicine_twice_does_not_interact_with_itself(kb, items):
    result = analyze(items("Panadol", "Calpol"), kb)
    assert not [w for w in result.warnings if w.category == "DDI"]


def test_all_pairs_in_a_longer_list_are_checked(kb, items):
    result = analyze(items("warfarin", "aspirin", "ibuprofen", "clopidogrel"), kb)
    found = {w.rule_id for w in result.warnings if w.category == "DDI"}
    # warfarin+aspirin, warfarin+ibuprofen, warfarin+clopidogrel,
    # aspirin+ibuprofen, aspirin+clopidogrel
    assert found == {"INT-0001", "INT-0002", "INT-0004", "INT-0012", "INT-0013"}


def test_relevant_and_matched_patient_factors(kb, items):
    meds = items("simvastatin", "clarithromycin")
    [w] = by_rule(analyze(meds, kb), "INT-0005")
    assert w.severity == "Contraindicated"
    assert w.relevant_factors == ("age_range:65_plus", "kidney_function:impaired")
    assert w.matched_factors == ()

    [w] = by_rule(analyze(meds, kb, {"age_range": "65_plus", "kidney_function": "normal"}), "INT-0005")
    assert w.matched_factors == ("age_range:65_plus",)
