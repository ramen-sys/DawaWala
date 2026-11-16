"""Class-level interaction rules (FR-8, BR-05): written once, expanded into medication pairs."""

import shutil

import pytest

from app.engine import ConfirmedItem, KBValidationError, analyze, load_kb
from app.engine.expansion import class_members, expand_class_interactions
from app.engine.models import (
    ClassInteractionRule,
    Medication,
    compute_components,
    expanded_rule_id,
    parent_of,
    product_ingredients,
)
from tests.conftest import FIXTURE_KB

HEADER = "rule_id,drug_a,drug_b,severity,description,relevant_factors,source,drug_a_class,drug_b_class\n"
# Extra fixture medications (ids continue after the 20 in fixtures/kb/medications.csv).
CELECOXIB, IBU_PSE, DICLO_GEL = 21, 22, 23
EXTRA_MEDS = (
    "21,celecoxib,NSAID,Celebrex\n"
    "22,ibuprofen + pseudoephedrine,NSAID,Arinac\n"
    "23,diclofenac (topical),NSAID,Voltral\n"
)
WARFARIN, IBUPROFEN, NAPROXEN, AMLODIPINE, SIMVA, ATORVA, CLOPIDOGREL = 5, 2, 3, 8, 12, 13, 6


@pytest.fixture
def kb_dir(tmp_path):
    target = tmp_path / "kb"
    shutil.copytree(FIXTURE_KB, target)
    with (target / "medications.csv").open("a", encoding="utf-8") as handle:
        handle.write(EXTRA_MEDS)
    # Rewrite interactions.csv with the optional class columns.
    old = (target / "interactions.csv").read_text(encoding="utf-8").splitlines()[1:]
    (target / "interactions.csv").write_text(HEADER + "".join(line + ",,\n" for line in old), encoding="utf-8")
    return target


def add_rules(kb_dir, *lines):
    with (kb_dir / "interactions.csv").open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def run(kb, *med_ids):
    return analyze([ConfirmedItem(i, m, kb.name(m)) for i, m in enumerate(med_ids)], kb)


def ddi(result):
    return [w for w in result.warnings if w.category == "DDI"]


def test_rule_id_helpers():
    assert expanded_rule_id("INT-0100", 5, 12) == "INT-0100/5-12"
    assert parent_of("INT-0100/5-12") == "INT-0100"
    assert parent_of("INT-0001") is None


def test_files_without_class_columns_still_load(kb):
    # The frozen fixture has no drug_a_class / drug_b_class columns.
    assert kb.class_interactions == ()
    assert all(r.parent_rule_id is None for rules in kb.interactions.values() for r in rules)


def test_medication_x_class_rule_is_expanded_and_fires(kb_dir):
    add_rules(kb_dir, "INT-0100,warfarin,,Major,NSAIDs with warfarin raise bleeding risk.,age_range:65_plus,src,,NSAID")
    kb = load_kb(kb_dir)

    (rule,) = kb.class_interactions
    assert (rule.a_medication, rule.b_class, rule.specificity) == (WARFARIN, "NSAID", 1)
    generated = {r.rule_id for rules in kb.interactions.values() for r in rules if r.parent_rule_id}
    # Ibuprofen and naproxen keep their own rules (INT-0002, INT-0003); the combination is covered
    # through its ibuprofen ingredient and the topical product is left out.
    assert generated == {expanded_rule_id("INT-0100", WARFARIN, CELECOXIB)}

    (warning,) = ddi(run(kb, CELECOXIB, WARFARIN))
    assert warning.rule_id == "INT-0100/5-21"
    assert warning.severity == "Major"
    assert warning.relevant_factors == ("age_range:65_plus",)
    assert warning.details == {"class_rule": "INT-0100"}


def test_exact_pair_rule_wins_over_class_rule(kb_dir):
    add_rules(kb_dir, "INT-0100,warfarin,,Minor,x,,src,,NSAID")
    (warning,) = ddi(run(load_kb(kb_dir), IBUPROFEN, WARFARIN))
    assert warning.rule_id == "INT-0002"
    assert warning.severity == "Major"


def test_combination_product_gets_one_warning_not_two(kb_dir):
    add_rules(kb_dir, "INT-0100,warfarin,,Major,x,,src,,NSAID")
    (warning,) = ddi(run(load_kb(kb_dir), IBU_PSE, WARFARIN))
    assert warning.rule_id == "INT-0002"
    assert warning.details == {"via": ["warfarin", "ibuprofen"]}


def test_local_products_are_not_expanded(kb_dir):
    add_rules(kb_dir, "INT-0100,warfarin,,Major,x,,src,,NSAID")
    assert ddi(run(load_kb(kb_dir), DICLO_GEL, WARFARIN)) == []


def test_class_x_class_rule_and_medication_x_class_precedence(kb_dir):
    add_rules(
        kb_dir,
        "INT-0200,,,Moderate,class rule,,src,calcium channel blocker,statin",
        "INT-0201,amlodipine,,Major,specific rule,,src,,statin",
    )
    kb = load_kb(kb_dir)
    simva = kb.interactions_for(AMLODIPINE, SIMVA)
    assert [r.rule_id for r in simva] == ["INT-0201/8-12"]  # medication x class beats class x class
    assert [r.rule_id for r in kb.interactions_for(AMLODIPINE, ATORVA)] == ["INT-0201/8-13"]
    assert [r.specificity for r in kb.class_interactions] == [0, 1]


def test_same_class_on_both_sides_pairs_distinct_members(kb_dir):
    add_rules(kb_dir, "INT-0300,,,Minor,two statins,,src,statin,statin")
    kb = load_kb(kb_dir)
    assert [r.rule_id for r in kb.interactions_for(SIMVA, ATORVA)] == ["INT-0300/12-13"]


def test_overlapping_rules_of_equal_specificity_are_rejected(kb_dir):
    add_rules(
        kb_dir,
        "INT-0400,amlodipine,,Major,x,,src,,statin",
        "INT-0401,simvastatin,,Minor,y,,src,,calcium channel blocker",
    )
    with pytest.raises(KBValidationError, match="INT-0400 and INT-0401 both cover amlodipine \\+ simvastatin"):
        load_kb(kb_dir)


@pytest.mark.parametrize(
    "line, message",
    [
        ("INT-9001,warfarin,,Major,x,,s,,made-up class", "class 'made-up class' is not in drug_classes.csv"),
        ("INT-9002,warfarin,aspirin,Major,x,,s,,NSAID", "give drug_b or drug_b_class, not both"),
        ("INT-9003,,aspirin,Major,x,,s,,", "drug_a or drug_a_class is required"),
        ("INT-9004/1,warfarin,,Major,x,,s,,NSAID", "rule_id must not contain '/'"),
        ("INT-9005,warfarin,,Severe,x,,s,,NSAID", "severity must be one of"),
        ("INT-9006,unknownium,,Major,x,,s,,NSAID", "unknown medication 'unknownium'"),
    ],
)
def test_class_rule_errors(kb_dir, line, message):
    add_rules(kb_dir, line)
    with pytest.raises(KBValidationError) as info:
        load_kb(kb_dir)
    assert message in "\n".join(info.value.errors)


def test_class_members_direct():
    meds = {
        1: Medication(1, "Ibuprofen", ("NSAID",), (), product_ingredients("Ibuprofen", None)),
        2: Medication(2, "Ibuprofen + Pseudoephedrine", ("NSAID",), (),
                      product_ingredients("x", ["Ibuprofen", "Pseudoephedrine"])),
        3: Medication(3, "Diclofenac (topical)", ("NSAID",), (), product_ingredients("Diclofenac (topical)", None)),
        4: Medication(4, "Pseudoephedrine + Caffeine", ("NSAID",), (),
                      product_ingredients("Pseudoephedrine + Caffeine", None)),
    }
    components = compute_components(meds)
    assert class_members(None, "NSAID", meds, components) == [1, 4]
    assert class_members(3, None, meds, components) == [3]


def test_expansion_returns_sorted_rules_and_reports_no_match():
    meds = {1: Medication(1, "A", ("X",), (), ("A",)), 2: Medication(2, "B", ("Y",), (), ("B",))}
    rule = ClassInteractionRule("INT-1", None, "X", None, "Z", "Minor", "d", (), "s")
    generated, errors = expand_class_interactions([rule], meds, {}, [])
    assert (generated, errors) == ([], [])
