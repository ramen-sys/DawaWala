"""FR-9: duplicate medication detection."""

from app.engine import analyze
from tests.conftest import by_rule


def test_two_brands_of_the_same_medicine(kb, items):
    [w] = by_rule(analyze(items("Panadol", "Calpol"), kb), "DUP-EXACT")
    assert w.category == "duplicate"
    assert w.medication_names == ("paracetamol",)
    assert w.details == {"kind": "exact", "entered_as": ["Calpol", "Panadol"]}
    assert w.severity is None


def test_same_medicine_three_times_is_one_warning(kb, items):
    [w] = by_rule(analyze(items("paracetamol", "Panadol", "Calpol"), kb), "DUP-EXACT")
    assert len(w.details["entered_as"]) == 3
    assert "3 times" in w.description


def test_therapeutic_duplication_same_class(kb, items):
    [w] = by_rule(analyze(items("ibuprofen", "naproxen"), kb), "DUP-CLASS:NSAID")
    assert w.details == {"kind": "therapeutic", "drug_class": "NSAID"}
    assert set(w.medication_names) == {"ibuprofen", "naproxen"}


def test_class_not_marked_duplication_relevant_is_ignored(kb, items):
    # aspirin + clopidogrel are both antiplatelets, often prescribed together.
    result = analyze(items("aspirin", "clopidogrel"), kb)
    assert not [w for w in result.warnings if w.category == "duplicate"]


def test_exact_duplicate_is_not_also_a_therapeutic_duplicate(kb, items):
    result = analyze(items("Brufen", "Advil"), kb)
    kinds = [w.details["kind"] for w in result.warnings if w.category == "duplicate"]
    assert kinds == ["exact"]


def test_class_with_three_members_lists_all(kb, items):
    meds = items("omeprazole", "esomeprazole", "Risek")
    result = analyze(meds, kb)
    [w] = by_rule(result, "DUP-CLASS:proton pump inhibitor")
    assert set(w.medication_names) == {"omeprazole", "esomeprazole"}
    assert by_rule(result, "DUP-EXACT")  # omeprazole + Risek
