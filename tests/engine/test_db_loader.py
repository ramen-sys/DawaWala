"""The database loader feeds the same detectors used for the CSV knowledge base."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.engine import ConfirmedItem, analyze, load_kb_from_db
from app.engine.db_loader import RISK_FACTORS
from app.engine.loader import KBValidationError
from app.models import CascadeRule, Contraindication, DrugInteraction, Medication, MedicationAlias
from app.models.enums import FactorType, Severity

SRC = "test fixture"


def _med(db, name):
    return db.scalar(select(Medication).where(Medication.standard_name == name))


def test_database_rules_drive_all_four_checks(db):
    para, ibu = _med(db, "Paracetamol"), _med(db, "Ibuprofen")
    nap = Medication(standard_name="Naproxen", drug_class="NSAID", source=SRC,
                     aliases=[MedicationAlias(alias="Naprosyn")])
    db.add(nap)
    db.flush()

    low, high = sorted((para.id, ibu.id))
    db.add(DrugInteraction(
        rule_code="INT-T001", drug_a_id=low, drug_b_id=high, source=SRC,
        description="These two together can irritate the stomach.",
        severity=Severity.MAJOR,
        relevant_risk_factors=["age_range:65_plus", "liver_function:impaired"],
    ))
    db.add(Contraindication(
        rule_code="CI-T001", medication_id=ibu.id, source=SRC,
        factor_type=FactorType.KIDNEY_FUNCTION, factor_value="impaired",
        description="Ibuprofen can make kidney problems worse.",
        severity=Severity.MAJOR, relevant_risk_factors=["age_range:65_plus"],
    ))
    db.add(Contraindication(
        rule_code="CI-T002", medication_id=para.id, source=SRC,
        factor_type=FactorType.LIVER_FUNCTION, factor_value="impaired",
        description="Liver disease can make paracetamol more harmful.",
        severity=Severity.MODERATE,
    ))
    db.add(CascadeRule(
        rule_code="CAS-T001", symptom_pattern="raised blood pressure", source=SRC,
        triggering_medications=[ibu], downstream_medications=[nap], relevant_risk_factors=["age_range:65_plus"],
        description="A painkiller can raise blood pressure, which is sometimes treated with another medicine.",
    ))
    db.flush()

    kb = load_kb_from_db(db, version="test", updated="2026-10-22", duplication_relevant={"NSAID"})
    assert set(kb.medications[para.id].aliases) == {"Panadol", "Calpol"}

    result = analyze(
        [
            ConfirmedItem(1, para.id, "Panadol"),
            ConfirmedItem(2, para.id, "Calpol"),
            ConfirmedItem(3, ibu.id, "Brufen"),
            ConfirmedItem(4, nap.id, "Naprosyn"),
        ],
        kb,
        {"age_range": "65_plus", "kidney_function": "impaired"},
    )
    rule_ids = {w.rule_id for w in result.warnings}
    assert {"INT-T001", "CI-T001", "CAS-T001", "DUP-EXACT", "DUP-CLASS:NSAID"} <= rule_ids

    interaction = next(w for w in result.warnings if w.rule_id == "INT-T001")
    assert interaction.severity == "Major"
    assert interaction.relevant_factors == ("age_range:65_plus", "liver_function:impaired")
    assert interaction.matched_factors == ("age_range:65_plus",)

    contra = next(w for w in result.warnings if w.rule_id == "CI-T001")
    assert contra.matched_factors == ("age_range:65_plus",)
    assert contra.details == {"condition": "kidney_function:impaired"}

    cascade = next(w for w in result.warnings if w.rule_id == "CAS-T001")
    assert cascade.details["trigger_ids"] == [ibu.id]
    assert cascade.details["downstream_ids"] == [nap.id]
    assert cascade.matched_factors == ("age_range:65_plus",)

    therapeutic = next(w for w in result.warnings if w.rule_id == "DUP-CLASS:NSAID")
    assert set(therapeutic.medication_ids) == {ibu.id, nap.id}

    # Liver function not given -> paracetamol rule is listed as not assessed, not dropped.
    assert [(n.rule_id, n.missing_factor) for n in result.not_assessed] == [("CI-T002", "liver_function")]


def test_defaults_come_from_settings(db):
    from app.core.config import settings

    kb = load_kb_from_db(db)
    assert kb.version == settings.KB_VERSION
    assert kb.updated == settings.KB_UPDATED_ON
    assert kb.risk_factors == RISK_FACTORS
    assert "unknown" not in RISK_FACTORS["age_range"]


# --------------------------------------------------------------------------
# Defensive validation. The database CHECK constraints and foreign keys
# already reject these rows, so they are fed through a fake session.
# --------------------------------------------------------------------------


class FakeSession:
    def __init__(self, meds=(), interactions=(), contraindications=(), cascades=()):
        self.rows = {
            "Medication": list(meds),
            "DrugInteraction": list(interactions),
            "Contraindication": list(contraindications),
            "CascadeRule": list(cascades),
        }

    def scalars(self, stmt):
        return self.rows[stmt.column_descriptions[0]["entity"].__name__]


def fake_med(med_id, name, drug_class=None):
    return SimpleNamespace(id=med_id, standard_name=name, drug_class=drug_class, alias_names=[name.upper(), ""],
                           medication_info=None)


def fake_interaction(code, a, b, severity="major", factors=()):
    return SimpleNamespace(rule_code=code, drug_a_id=a, drug_b_id=b, severity=severity,
                           relevant_risk_factors=list(factors), description="d", source=SRC)


def fake_contra(code, med_id, factor="kidney_function", value="impaired", severity="major", factors=()):
    return SimpleNamespace(rule_code=code, medication_id=med_id, factor_type=factor, factor_value=value,
                           severity=severity, relevant_risk_factors=list(factors), description="d", source=SRC)


def fake_cascade(code, triggers, downstream, symptom="swelling", factors=()):
    return SimpleNamespace(rule_code=code, symptom_pattern=symptom, description="d", source=SRC,
                           relevant_risk_factors=list(factors),
                           triggering_medications=[SimpleNamespace(id=i) for i in triggers],
                           downstream_medications=[SimpleNamespace(id=i) for i in downstream])


MEDS = [fake_med(1, "alpha", "NSAID"), fake_med(2, "beta", "NSAID"), fake_med(3, "gamma")]


def load(session, **kwargs):
    kwargs.setdefault("version", "t")
    kwargs.setdefault("updated", "2026-10-22")
    kwargs.setdefault("duplication_relevant", {"NSAID"})
    return load_kb_from_db(session, **kwargs)


def test_fake_session_valid_rows_load():
    kb = load(FakeSession(
        MEDS,
        [fake_interaction("INT-1", 2, 1, severity=Severity.MODERATE, factors=["age_range: 65_PLUS"])],
        [fake_contra("CI-1", 3, factor=FactorType.LIVER_FUNCTION)],
        [fake_cascade("CAS-2", [1], [2]), fake_cascade("CAS-1", [2], [3])],
    ))
    assert kb.medications[1].aliases == ("ALPHA",)
    assert kb.medications[3].classes == ()
    assert kb.classes["NSAID"].duplication_relevant
    (rule,) = kb.interactions_for(1, 2)
    assert (rule.drug_a, rule.drug_b, rule.severity) == (1, 2, "Moderate")
    assert rule.relevant_factors == (("age_range", "65_plus"),)
    assert kb.contraindications[3][0].factor == "liver_function"
    assert [c.rule_id for c in kb.cascades] == ["CAS-1", "CAS-2"]


@pytest.mark.parametrize(
    "session, message",
    [
        (FakeSession(MEDS, [fake_interaction("INT-1", 1, 2, factors=["age_range"])]), "must look like factor:value"),
        (FakeSession(MEDS, [fake_interaction("INT-1", 1, 2, factors=["blood:a"])]), "unknown risk factor 'blood'"),
        (FakeSession(MEDS, [fake_interaction("INT-1", 1, 2, factors=["age_range:old"])]), "'old' is not an allowed"),
        (FakeSession(MEDS, [fake_interaction("INT-1", 1, 9)]), "medication id is not in medications"),
        (FakeSession(MEDS, [fake_interaction("INT-1", 1, 1)]), "cannot interact with itself"),
        (FakeSession(MEDS, [fake_interaction("INT-1", 1, 2, severity="huge")]), "severity must be one of"),
        (FakeSession(MEDS, contraindications=[fake_contra("CI-1", 1, factor="other")]), "not a known risk factor"),
        (FakeSession(MEDS, contraindications=[fake_contra("CI-1", 1, value="unknown")]), "not an allowed value"),
        (FakeSession(MEDS, contraindications=[fake_contra("CI-1", 1, factors=["kidney_function:normal"])]),
         "must not repeat the condition factor"),
        (FakeSession(MEDS, contraindications=[fake_contra("CI-1", 9)]), "medication id is not in medications"),
        (FakeSession(MEDS, contraindications=[fake_contra("CI-1", 1, severity=None)]), "severity must be one of"),
        (FakeSession(MEDS, cascades=[fake_cascade("CAS-1", [], [2])]), "needs at least one triggering"),
        (FakeSession(MEDS, cascades=[fake_cascade("CAS-1", [1], [])]), "needs at least one downstream"),
        (FakeSession(MEDS, cascades=[fake_cascade("CAS-1", [1], [2], symptom=" ")]), "symptom_pattern is required"),
        (FakeSession(MEDS, cascades=[fake_cascade("CAS-1", [1], [2], factors=["age"])]), "must look like factor:value"),
    ],
)
def test_invalid_rows_are_rejected(session, message):
    with pytest.raises(KBValidationError, match=message):
        load(session)


def test_invalid_version_and_date_are_rejected():
    with pytest.raises(KBValidationError) as exc:
        load(FakeSession(MEDS), version=" ", updated="22/10/2026")
    assert "kb version is required" in str(exc.value)
    assert "kb updated date" in str(exc.value)
