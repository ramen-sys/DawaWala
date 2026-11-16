"""Combination products are checked through their active ingredients (FR-8, FR-9, FR-10, FR-12)."""

import pytest

from app.engine import ConfirmedItem, analyze
from app.engine.models import (
    CascadeRule,
    ContraindicationRule,
    DrugClass,
    InteractionRule,
    KnowledgeBase,
    Medication,
    is_local_product,
    product_ingredients,
)

IBU, WARF, IBU_PSE, PARA_PSE, IBU_GEL, LISI, NAP = 1, 2, 3, 4, 5, 6, 7


def _med(med_id, name, cls, stored=None):
    return Medication(med_id, name, (cls,), (), product_ingredients(name, stored))


@pytest.fixture(scope="module")
def kb():
    meds = [
        _med(IBU, "Ibuprofen", "NSAID"),
        _med(WARF, "Warfarin", "Anticoagulant"),
        _med(IBU_PSE, "Ibuprofen + Pseudoephedrine", "NSAID", ["Ibuprofen", "Pseudoephedrine"]),
        _med(PARA_PSE, "Paracetamol + Pseudoephedrine", "Analgesic", ["Paracetamol", " pseudoephedrine "]),
        _med(IBU_GEL, "Ibuprofen (topical)", "NSAID", ["Ibuprofen"]),
        _med(LISI, "Lisinopril", "ACE inhibitor"),
        _med(NAP, "Naproxen", "NSAID"),
    ]
    return KnowledgeBase(
        version="t",
        updated="2026-11-04",
        medications={m.medication_id: m for m in meds},
        classes={c: DrugClass(c, c == "NSAID") for c in ("NSAID", "Anticoagulant", "Analgesic", "ACE inhibitor")},
        risk_factors={"age_range": ("under_18", "18_64", "65_plus"), "kidney_function": ("normal", "impaired")},
        interactions={(IBU, WARF): (
            InteractionRule("INT-1", IBU, WARF, "Major", "bleeding", (("age_range", "65_plus"),), "t"),
        )},
        contraindications={IBU: (
            ContraindicationRule("CI-1", IBU, "kidney_function", "impaired", "Major", "kidneys", (), "t"),
        )},
        cascades=(CascadeRule("CAS-1", frozenset({IBU}), frozenset(), "raised blood pressure",
                              frozenset({LISI}), frozenset(), "bp", (), "t"),),
    )


def run(kb, *med_ids, factors=None):
    items = [ConfirmedItem(i, m, kb.name(m)) for i, m in enumerate(med_ids)]
    return analyze(items, kb, factors)


def rules(result):
    return {w.rule_id: w for w in result.warnings}


def test_ingredient_helpers():
    assert product_ingredients("Paracetamol + Caffeine", None) == ("Paracetamol", "Caffeine")
    assert product_ingredients("Clobetasol (topical)", ["Clobetasol propionate"]) == ()
    assert product_ingredients("Vitamin B", ["Thiamine", "", " "]) == ("Thiamine",)
    assert is_local_product("Polymyxin B + Bacitracin (eye)")
    assert is_local_product("Choline salicylate + Lidocaine (oral gel)")
    assert not is_local_product("Ibuprofen")


def test_components_use_single_ingredient_medications_only(kb):
    assert kb.components == {IBU_PSE: (IBU,)}
    assert kb.with_components(IBU_PSE) == (IBU_PSE, IBU)
    assert kb.with_components(WARF) == (WARF,)


def test_combination_inherits_interaction(kb):
    direct = rules(run(kb, IBU, WARF))["INT-1"]
    assert direct.details == {}
    via = rules(run(kb, IBU_PSE, WARF, factors={"age_range": "65_plus"}))["INT-1"]
    assert via.medication_names == ("Warfarin", "Ibuprofen + Pseudoephedrine")  # ordered by id
    assert via.details == {"via": ["Warfarin", "Ibuprofen"]}
    assert via.matched_factors == ("age_range:65_plus",)


def test_shared_ingredient_is_a_duplicate_not_an_interaction(kb):
    found = rules(run(kb, IBU, IBU_PSE))
    assert not any(w.category == "DDI" for w in found.values())
    dup = found["DUP-INGREDIENT:Ibuprofen"]
    assert dup.details == {"kind": "exact", "ingredient": "Ibuprofen"}
    assert dup.medication_ids == (IBU, IBU_PSE)
    # Same pair already reported as a shared ingredient: no extra NSAID class warning.
    assert "DUP-CLASS:NSAID" not in found


def test_class_warning_kept_when_a_member_does_not_share_the_ingredient(kb):
    found = rules(run(kb, IBU, IBU_PSE, NAP))
    assert "DUP-INGREDIENT:Ibuprofen" in found
    assert found["DUP-CLASS:NSAID"].medication_ids == (IBU, IBU_PSE, NAP)


def test_two_combinations_sharing_an_ingredient(kb):
    found = rules(run(kb, IBU_PSE, PARA_PSE))
    assert found["DUP-INGREDIENT:Pseudoephedrine"].medication_ids == (IBU_PSE, PARA_PSE)


def test_local_products_are_not_matched_by_ingredient(kb):
    found = rules(run(kb, IBU_GEL, IBU, WARF))
    assert not any(rule.startswith("DUP-INGREDIENT") for rule in found)
    assert found["DUP-CLASS:NSAID"].medication_ids == (IBU, IBU_GEL)
    assert [w.medication_ids for w in found.values() if w.category == "DDI"] == [(IBU, WARF)]


def test_combination_inherits_contraindication(kb):
    result = run(kb, IBU_PSE, factors={"kidney_function": "impaired"})
    warning = rules(result)["CI-1"]
    assert warning.medication_ids == (IBU_PSE,)
    assert warning.details == {"condition": "kidney_function:impaired", "via": "Ibuprofen"}

    unknown = run(kb, IBU_PSE)
    assert [(n.rule_id, n.medication_id) for n in unknown.not_assessed] == [("CI-1", IBU_PSE)]


def test_combination_matches_cascade(kb):
    cascade = rules(run(kb, IBU_PSE, LISI))["CAS-1"]
    assert cascade.details["trigger_ids"] == [IBU_PSE]
    assert cascade.details["downstream_ids"] == [LISI]
