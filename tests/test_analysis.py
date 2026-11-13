"""Analysis API (FR-8 to FR-15): the safety engine wired to medication lists."""

from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.engine import KBValidationError, SafetyWarning
from app.engine.models import (
    CascadeRule,
    ContraindicationRule,
    DrugClass,
    InteractionRule,
    KnowledgeBase,
    Medication,
    product_ingredients,
)
from app.main import app
from app.models import Medication as MedicationRow
from app.models.enums import SeverityBand
from app.routers.analysis import knowledge_base
from app.services import analysis_service, explanations, knowledge_base_service, scoring

FORBIDDEN_WORDS = ("safe", "stop taking", "start taking", "change your dose")


@pytest.fixture(scope="module")
def med_ids(session_factory):
    with session_factory() as db:
        rows = db.scalars(select(MedicationRow).where(
            MedicationRow.standard_name.in_(["Paracetamol", "Ibuprofen", "Omeprazole"]))).all()
        return {row.standard_name: row.id for row in rows}


@pytest.fixture(scope="module")
def test_kb(med_ids):
    para, ibu, omep = med_ids["Paracetamol"], med_ids["Ibuprofen"], med_ids["Omeprazole"]
    meds = {
        para: Medication(para, "Paracetamol", ("Analgesic / antipyretic",), ("Panadol", "Calpol"),
                         product_ingredients("Paracetamol", None)),
        ibu: Medication(ibu, "Ibuprofen", ("NSAID",), ("Brufen",), product_ingredients("Ibuprofen", None)),
        omep: Medication(omep, "Omeprazole", ("Proton-pump inhibitor",), ("Risek",),
                         product_ingredients("Omeprazole", None)),
    }
    low, high = sorted((para, ibu))
    return KnowledgeBase(
        version="9.9.9",
        updated=date.today().isoformat(),
        medications=meds,
        classes={c: DrugClass(c, c == "NSAID") for c in ("Analgesic / antipyretic", "NSAID", "Proton-pump inhibitor")},
        risk_factors={"age_range": ("under_18", "18_64", "65_plus"), "kidney_function": ("normal", "impaired"),
                      "liver_function": ("normal", "impaired")},
        interactions={(low, high): (InteractionRule(
            "INT-T1", low, high, "Major", "Together these can upset the stomach.", (("age_range", "65_plus"),), "t"),)},
        contraindications={
            ibu: (ContraindicationRule("CI-T1", ibu, "kidney_function", "impaired", "Major",
                                       "Ibuprofen can make kidney problems worse.", (("age_range", "65_plus"),), "t"),),
            para: (ContraindicationRule("CI-T2", para, "liver_function", "impaired", "Moderate",
                                        "Liver disease can make paracetamol more harmful.", (), "t"),),
        },
        cascades=(CascadeRule("CAS-T1", frozenset({ibu}), frozenset(), "stomach upset", frozenset({omep}),
                              frozenset(), "Painkillers may upset the stomach, which is sometimes treated "
                              "with a stomach medicine.", (("age_range", "65_plus"),), "t"),),
    )


@pytest.fixture
def use_kb(test_kb):
    app.dependency_overrides[knowledge_base] = lambda: test_kb
    yield test_kb
    app.dependency_overrides.pop(knowledge_base, None)


def confirmed_list(client, headers, med_ids, names, unrecognised=()):
    """Create a list, accept each name as the given medicine (None = keep unrecognised), confirm it."""
    entered = list(names) + list(unrecognised)
    r = client.post("/api/v1/medication-lists", json={"names": entered}, headers=headers)
    assert r.status_code == 201, r.text
    data = r.json()
    for item, name in zip(data["items"], entered, strict=True):
        if name in unrecognised:
            r = client.post(f"/api/v1/medication-lists/{data['id']}/items/{item['id']}/keep-unrecognised",
                            headers=headers)
        else:
            r = client.post(f"/api/v1/medication-lists/{data['id']}/items/{item['id']}/accept",
                            json={"medication_id": med_ids[names[name]]}, headers=headers)
        assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/medication-lists/{data['id']}/confirm", headers=headers)
    assert r.status_code == 200, r.text
    return data["id"]


FULL = {"Panadol": "Paracetamol", "Calpol": "Paracetamol", "Brufen": "Ibuprofen", "Risek": "Omeprazole"}


def test_unconfirmed_list_is_never_analysed(client, make_user, use_kb):
    _, headers = make_user()
    r = client.post("/api/v1/medication-lists", json={"names": ["Panadol", "Brufen"]}, headers=headers)
    r = client.post(f"/api/v1/medication-lists/{r.json()['id']}/analyses", headers=headers)
    assert r.status_code == 409
    assert r.json()["code"] == "list_not_confirmed"


def test_full_analysis_is_scored_ranked_explained_and_stored(client, make_user, med_ids, use_kb):
    _, headers = make_user()
    list_id = confirmed_list(client, headers, med_ids, FULL, unrecognised=["Vitamin D drops"])
    r = client.put(f"/api/v1/medication-lists/{list_id}/risk-factors",
                   json={"age_range": "65_plus", "kidney_function": "impaired"}, headers=headers)
    assert r.status_code == 200
    assert r.json() == {"age_range": "65_plus", "kidney_function": "impaired", "liver_function": "unknown",
                        "analysis_outdated": False}

    r = client.post(f"/api/v1/medication-lists/{list_id}/analyses", headers=headers)
    assert r.status_code == 201, r.text
    result = r.json()

    assert result["disclaimer"] == analysis_service.DISCLAIMER
    assert (result["kb_version"], result["kb_stale"], result["freshness"]) == ("9.9.9", False, "current")
    assert result["no_warnings_message"] is None
    assert result["risk_factors"]["age_range"] == "65_plus"

    # FR-11 order: 55 (contraindication before DDI), then 30 (cascade before duplicate).
    ranked = [(w["category"], w["rule_id"], w["score"], w["severity_band"]) for w in result["warnings"]]
    assert ranked == [
        ("contraindication", "CI-T1", 55, "high"),
        ("ddi", "INT-T1", 55, "high"),
        ("cascade", "CAS-T1", 30, "moderate"),
        ("duplicate", "DUP-EXACT", 30, "moderate"),
    ]
    assert result["band_counts"] == {"low": 0, "moderate": 2, "high": 2, "critical": 0}
    for w in result["warnings"]:
        assert sum(f["points"] for f in w["score_factors"]) == w["score"]  # QA-EXP-02
        text = w["explanation"]
        assert w["rule_id"] in text and "9.9.9" in text and "doctor or pharmacist" in text
        assert len(text.split()) <= settings.EXPLANATION_MAX_WORDS
        assert not any(word in text.lower() for word in FORBIDDEN_WORDS)
    ci = result["warnings"][0]
    assert ci["score_factors"] == [{"factor": "Rule severity (contraindication): Major", "points": 50},
                                   {"factor": "Patient factor: Age 65 or over", "points": 5}]
    assert ci["medications"] == [{"id": med_ids["Ibuprofen"], "name": "Ibuprofen"}]
    assert ci["details"]["rule_severity"] == "Major"
    assert "only a possibility" in result["warnings"][2]["explanation"]  # cascades are never a diagnosis

    assert [n["entered_text"] for n in result["not_analysed"]] == ["Vitamin D drops"]
    assert [(n["rule_id"], n["missing_factor"]) for n in result["not_assessed"]] == [("CI-T2", "liver_function")]

    # FR-15: reopening shows exactly the same result, and history lists it.
    again = client.get(f"/api/v1/medication-lists/{list_id}/analyses/{result['id']}", headers=headers).json()
    assert again == result
    history = client.get(f"/api/v1/medication-lists/{list_id}/analyses", headers=headers).json()
    assert [(h["id"], h["warning_count"]) for h in history] == [(result["id"], 4)]


def test_changing_risk_factors_outdates_the_analysis(client, make_user, med_ids, use_kb):
    _, headers = make_user()
    list_id = confirmed_list(client, headers, med_ids, {"Brufen": "Ibuprofen"})
    first = client.post(f"/api/v1/medication-lists/{list_id}/analyses", headers=headers).json()
    assert [n["rule_id"] for n in first["not_assessed"]] == ["CI-T1"]

    same = client.put(f"/api/v1/medication-lists/{list_id}/risk-factors", json={}, headers=headers).json()
    assert same["analysis_outdated"] is False  # nothing changed
    changed = client.put(f"/api/v1/medication-lists/{list_id}/risk-factors",
                         json={"kidney_function": "impaired"}, headers=headers).json()
    assert changed["analysis_outdated"] is True
    assert client.get(f"/api/v1/medication-lists/{list_id}/analyses/{first['id']}",
                      headers=headers).json()["freshness"] == "outdated"
    assert client.get(f"/api/v1/medication-lists/{list_id}/risk-factors", headers=headers).json() == {
        "age_range": "unknown", "kidney_function": "impaired", "liver_function": "unknown"}

    second = client.post(f"/api/v1/medication-lists/{list_id}/analyses", headers=headers).json()
    assert [w["rule_id"] for w in second["warnings"]] == ["CI-T1"]
    history = client.get(f"/api/v1/medication-lists/{list_id}/analyses", headers=headers).json()
    assert [(h["id"], h["freshness"]) for h in history] == [(second["id"], "current"), (first["id"], "outdated")]


def test_no_warnings_never_says_safe(client, make_user, med_ids, use_kb):
    _, headers = make_user()
    list_id = confirmed_list(client, headers, med_ids, {"Risek": "Omeprazole"})
    result = client.post(f"/api/v1/medication-lists/{list_id}/analyses", headers=headers).json()
    assert result["warnings"] == []
    assert result["no_warnings_message"] == analysis_service.NO_WARNINGS_MESSAGE


def test_invalid_risk_factor_is_rejected(client, make_user, med_ids, use_kb):
    _, headers = make_user()
    list_id = confirmed_list(client, headers, med_ids, {"Risek": "Omeprazole"})
    for body in ({"age_range": "old"}, {"blood_group": "A"}):
        r = client.put(f"/api/v1/medication-lists/{list_id}/risk-factors", json=body, headers=headers)
        assert r.status_code == 422


def test_other_users_and_missing_analyses(client, make_user, med_ids, use_kb):
    _, owner = make_user()
    _, other = make_user()
    list_id = confirmed_list(client, owner, med_ids, {"Risek": "Omeprazole"})
    for method, path in [("post", "analyses"), ("get", "analyses"), ("get", "risk-factors")]:
        r = getattr(client, method)(f"/api/v1/medication-lists/{list_id}/{path}", headers=other)
        assert r.status_code == 403
    r = client.get(f"/api/v1/medication-lists/{list_id}/analyses/999999", headers=owner)
    assert r.status_code == 404
    assert r.json()["code"] == "analysis_not_found"


def test_knowledge_base_is_loaded_cached_and_reloaded_by_admin(client, make_user, med_ids, monkeypatch):
    knowledge_base_service.clear_cache()
    try:
        _, user = make_user()
        _, admin = make_user(role="admin")
        list_id = confirmed_list(client, user, med_ids, {"Risek": "Omeprazole"})
        # No override: the real loader reads the (test-schema) database once and caches it.
        assert client.post(f"/api/v1/medication-lists/{list_id}/analyses", headers=user).status_code == 201
        cached = knowledge_base_service._cached
        assert cached is not None
        assert client.post(f"/api/v1/medication-lists/{list_id}/analyses", headers=user).status_code == 201
        assert knowledge_base_service._cached is cached

        assert client.post("/api/v1/medications/knowledge-base/reload", headers=user).status_code == 403
        r = client.post("/api/v1/medications/knowledge-base/reload", headers=admin)
        assert r.status_code == 200
        assert r.json()["version"] == settings.KB_VERSION
        assert knowledge_base_service._cached is not cached

        def broken(_db):
            raise KBValidationError(["bad row"])

        monkeypatch.setattr(knowledge_base_service, "load_kb_from_db", broken)
        knowledge_base_service.clear_cache()
        r = client.post(f"/api/v1/medication-lists/{list_id}/analyses", headers=user)
        assert r.status_code == 503
        assert r.json()["code"] == "knowledge_base_unavailable"
    finally:
        knowledge_base_service.clear_cache()


# --------------------------------------------------------------------------
# Scoring (FR-11) and explanations (FR-13) as units
# --------------------------------------------------------------------------


def warning(category="DDI", severity="Major", matched=(), details=None, description="Reason.", names=("A", "B")):
    return SafetyWarning(category=category, rule_id="R-1", medication_ids=tuple(range(len(names))),
                         medication_names=names, severity=severity, description=description,
                         relevant_factors=matched, matched_factors=matched, kb_version="1.2",
                         details=details or {})


@pytest.mark.parametrize("score, band", [(0, SeverityBand.LOW), (24, SeverityBand.LOW), (25, SeverityBand.MODERATE),
                                         (50, SeverityBand.HIGH), (75, SeverityBand.CRITICAL),
                                         (100, SeverityBand.CRITICAL)])
def test_bands(score, band):
    assert scoring.band_for(score) == band


def test_srs_examples_and_factor_rules():
    every = ("age_range:65_plus", "kidney_function:impaired", "liver_function:impaired")
    # SRS 5.5: contraindicated (70) with two relevant factors scores 80, Critical.
    s = scoring.score_warning(warning(severity="Contraindicated", matched=every[:2]))
    assert (s.score, s.band) == (80, SeverityBand.CRITICAL)
    # A cascade (25) with one relevant factor scores 30, Moderate.
    s = scoring.score_warning(warning(category="cascade", severity=None, matched=every[:1]))
    assert (s.score, s.band) == (30, SeverityBand.MODERATE)
    # Only the three Table 5.2 factors earn points, each once.
    s = scoring.score_warning(warning(severity="Minor", matched=("age_range:under_18", every[0], every[0])))
    assert [f["points"] for f in s.factors] == [10, 5]
    s = scoring.score_warning(warning(category="duplicate", severity=None, details={"kind": "therapeutic"}))
    assert s.score == 15
    s = scoring.score_warning(warning(category="duplicate", severity=None, details={"kind": "exact"}))
    assert s.score == 30


def test_factor_budget_and_cap(monkeypatch):
    every = ("age_range:65_plus", "kidney_function:impaired", "liver_function:impaired")
    monkeypatch.setattr(settings, "SCORE_PATIENT_FACTOR_MAX", 7)
    s = scoring.score_warning(warning(severity="Minor", matched=every))
    assert [f["points"] for f in s.factors] == [10, 5, 2]
    monkeypatch.setattr(settings, "SCORE_SEVERITY_CONTRAINDICATED", 99)
    s = scoring.score_warning(warning(severity="Contraindicated", matched=every))
    assert s.score == 100  # capped; the items still show what produced it
    assert sum(f["points"] for f in s.factors) == 106


@pytest.mark.parametrize(
    "w, expected",
    [
        (warning(details={"via": ["Ibuprofen", "Warfarin"]}), "The rule is about Ibuprofen and Warfarin"),
        (warning(category="contraindication", names=("Arinac",),
                 details={"condition": "kidney_function:impaired", "via": "Ibuprofen"}),
         "Arinac may not be suitable for a patient with reduced kidney function. It contains Ibuprofen."),
        (warning(category="duplicate", details={"kind": "therapeutic", "drug_class": "NSAID"}),
         "A and B belong to the same group of medicines (NSAID)"),
        (warning(category="duplicate", details={"kind": "exact", "ingredient": "Paracetamol"}),
         "A and B all contain Paracetamol."),
        (warning(category="duplicate", names=("A",), details={"kind": "exact"}), "A is listed more than once."),
        (warning(matched=("age_range:65_plus", "blood_group:o")), "because of being 65 or over and blood group: o."),
    ],
)
def test_explanation_wording(w, expected):
    assert expected in explanations.explain(w)


def test_long_explanation_keeps_rule_and_advice():
    text = explanations.explain(warning(description="word " * 400))
    assert len(text.split()) <= settings.EXPLANATION_MAX_WORDS
    assert text.endswith("Rule R-1, knowledge base version 1.2. " + explanations.CONSULT)


def test_stale_knowledge_base():
    today = date(2026, 11, 12)
    assert not analysis_service.is_stale("2026-11-04", today)
    assert analysis_service.is_stale("2026-01-01", today)
    assert analysis_service.is_stale("not a date", today)
