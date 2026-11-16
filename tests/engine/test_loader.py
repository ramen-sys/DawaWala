"""The loader must catch curation mistakes and report all of them."""

import json
import shutil

import pytest

from app.engine import KBValidationError, load_kb
from tests.conftest import FIXTURE_KB


@pytest.fixture
def kb_dir(tmp_path):
    target = tmp_path / "kb"
    shutil.copytree(FIXTURE_KB, target)
    return target


def append(path, line):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def errors_for(kb_dir):
    with pytest.raises(KBValidationError) as info:
        load_kb(kb_dir)
    return "\n".join(info.value.errors)


def test_fixture_kb_loads(kb):
    assert kb.interactions_for(5, 4) == kb.interactions_for(4, 5)


def test_pair_written_in_reverse_is_stored_canonically(kb):
    # interactions.csv lists "warfarin,aspirin" (5,4); lookup works both ways.
    [rule] = kb.interactions_for(4, 5)
    assert (rule.drug_a, rule.drug_b) == (4, 5)


def test_byte_order_mark_is_ignored(kb_dir):
    path = kb_dir / "risk_factors.csv"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert "kidney_function" in load_kb(kb_dir).risk_factors


def test_blank_lines_are_skipped(kb_dir):
    append(kb_dir / "interactions.csv", ",,,,,,")
    load_kb(kb_dir)


@pytest.mark.parametrize(
    "line, message",
    [
        ("INT-9001,warfarin,unknownium,Major,x,,s", "unknown medication 'unknownium'"),
        ("INT-9002,warfarin,Disprin,Major,x,,s", "use the standard name 'aspirin'"),
        ("INT-9003,warfarin,aspirin,Severe,x,,s", "severity must be one of"),
        ("INT-9004,warfarin,warfarin,Major,x,,s", "cannot interact with itself"),
        ("INT-0001,metformin,aspirin,Major,x,,s", "rule_id INT-0001 is used twice"),
        ("INT-9005,metformin,aspirin,Major,x,blood_group:A,s", "unknown risk factor 'blood_group'"),
        ("INT-9006,metformin,aspirin,Major,x,age_range:old,s", "'old' is not an allowed value"),
        (",metformin,aspirin,Major,x,,s", "rule_id is required"),
    ],
)
def test_interaction_errors(kb_dir, line, message):
    append(kb_dir / "interactions.csv", line)
    assert message in errors_for(kb_dir)


@pytest.mark.parametrize(
    "line, message",
    [
        ("CI-9001,metformin,blood_group,A,Major,x,,s", "unknown risk factor 'blood_group'"),
        ("CI-9002,metformin,kidney_function,bad,Major,x,,s", "'bad' is not an allowed value"),
        ("CI-9003,metformin,kidney_function,impaired,Major,x,kidney_function:impaired,s",
         "must not repeat the condition"),
        ("CI-9004,unknownium,kidney_function,impaired,Major,x,,s", "unknown medication"),
    ],
)
def test_contraindication_errors(kb_dir, line, message):
    append(kb_dir / "contraindications.csv", line)
    assert message in errors_for(kb_dir)


@pytest.mark.parametrize(
    "line, message",
    [
        ("CAS-9001,,,swelling,,loop diuretic,x,,s", "needs at least one trigger"),
        ("CAS-9002,amlodipine,,swelling,,,x,,s", "needs at least one downstream"),
        ("CAS-9003,,made-up class,swelling,,loop diuretic,x,,s", "class 'made-up class' is not in"),
        ("CAS-9004,amlodipine,,,,loop diuretic,x,,s", "symptom_pattern is required"),
        ("CAS-9005,unknownium,,swelling,,loop diuretic,x,,s", "unknown medication"),
    ],
)
def test_cascade_errors(kb_dir, line, message):
    append(kb_dir / "cascades.csv", line)
    assert message in errors_for(kb_dir)


@pytest.mark.parametrize(
    "line, message",
    [
        ("abc,newmed,analgesic,", "medication_id must be a whole number"),
        ("1,newmed,analgesic,", "medication_id 1 is used twice"),
        ("99,paracetamol,analgesic,", "standard name 'paracetamol' is used twice"),
        ("99,,analgesic,", "standard_name is required"),
        ("99,newmed,made-up class,", "class 'made-up class' is not in drug_classes.csv"),
        ("99,newmed,analgesic,Panadol", "alias 'Panadol' is used by both"),
        ("99,newmed,analgesic,ibuprofen", "is the standard name of another medication"),
    ],
)
def test_medication_errors(kb_dir, line, message):
    append(kb_dir / "medications.csv", line)
    assert message in errors_for(kb_dir)


@pytest.mark.parametrize(
    "line, message",
    [
        ("NSAID,true", "duplicate class 'NSAID'"),
        ("newclass,maybe", "duplication_relevant must be true or false"),
    ],
)
def test_class_errors(kb_dir, line, message):
    append(kb_dir / "drug_classes.csv", line)
    assert message in errors_for(kb_dir)


@pytest.mark.parametrize(
    "line, message",
    [
        ("blood_group,", "factor and allowed_values are required"),
        ("blood_group,A;unknown", "do not list 'unknown'"),
    ],
)
def test_risk_factor_errors(kb_dir, line, message):
    append(kb_dir / "risk_factors.csv", line)
    assert message in errors_for(kb_dir)


def test_all_errors_are_reported_together(kb_dir):
    append(kb_dir / "interactions.csv", "INT-9001,warfarin,unknownium,Major,x,,s")
    append(kb_dir / "contraindications.csv", "CI-9001,metformin,blood_group,A,Major,x,,s")
    with pytest.raises(KBValidationError) as info:
        load_kb(kb_dir)
    assert len(info.value.errors) == 2


def test_missing_file(kb_dir):
    (kb_dir / "cascades.csv").unlink()
    assert "cascades.csv: file is missing" in errors_for(kb_dir)


def test_missing_column(kb_dir):
    (kb_dir / "drug_classes.csv").write_text("class_name\nNSAID\n", encoding="utf-8")
    assert "missing column(s) duplication_relevant" in errors_for(kb_dir)


def test_missing_metadata_file(kb_dir):
    (kb_dir / "kb_meta.json").unlink()
    assert "kb_meta.json: file is missing" in errors_for(kb_dir)


def test_bad_metadata(kb_dir):
    (kb_dir / "kb_meta.json").write_text(json.dumps({"version": "", "updated": "soon"}))
    errors = errors_for(kb_dir)
    assert "'version' is required" in errors
    assert "'updated' must be a date" in errors
