"""The database loader feeds the same detectors used for the CSV knowledge base."""

import pytest
from sqlalchemy import select

from app.engine import ConfirmedItem, analyze, load_kb_from_db
from app.engine.loader import KBValidationError
from app.models import CascadeRule, Contraindication, DrugInteraction, Medication
from app.models.enums import Severity


def test_database_rules_drive_all_four_checks(db):
    para = db.scalar(select(Medication).where(Medication.standard_name == "Paracetamol"))
    ibu = db.scalar(select(Medication).where(Medication.standard_name == "Ibuprofen"))
    nap = Medication(standard_name="Naproxen", drug_class="NSAID", aliases=["Naprosyn"])
    db.add(nap)
    db.flush()

    low, high = sorted((para.id, ibu.id))
    db.add(DrugInteraction(
        drug_a_id=low,
        drug_b_id=high,
        description="These two together can irritate the stomach.",
        severity=Severity.MAJOR,
        relevant_risk_factors=["age_range:65_plus"],
    ))
    db.add(Contraindication(
        medication_id=ibu.id,
        patient_condition="kidney_function:impaired",
        description="Ibuprofen can make kidney problems worse.",
        severity=Severity.MAJOR,
    ))
    db.add(CascadeRule(
        triggering_medications=[ibu.id],
        symptom_pattern="raised blood pressure",
        downstream_medications=[nap.id],
        description="A painkiller can raise blood pressure, which is sometimes treated with another medicine.",
    ))
    db.flush()

    kb = load_kb_from_db(db, version="test", updated="2026-10-22", duplication_relevant={"NSAID"})
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
    categories = {warning.category for warning in result.warnings}
    assert categories == {"DDI", "duplicate", "contraindication", "cascade"}
    interaction = next(warning for warning in result.warnings if warning.category == "DDI")
    assert interaction.severity == "Major"
    assert interaction.matched_factors == ("age_range:65_plus",)
    exact = next(warning for warning in result.warnings if warning.rule_id == "DUP-EXACT")
    assert exact.details["kind"] == "exact"
    therapeutic = next(warning for warning in result.warnings if warning.rule_id == "DUP-CLASS:NSAID")
    assert set(therapeutic.medication_ids) == {ibu.id, nap.id}


def test_unknown_condition_is_rejected(db):
    para = db.scalar(select(Medication).where(Medication.standard_name == "Paracetamol"))
    db.add(Contraindication(
        medication_id=para.id,
        patient_condition="blood_group:A",
        description="Not a supported factor.",
        severity=Severity.MINOR,
    ))
    db.flush()
    with pytest.raises(KBValidationError):
        load_kb_from_db(db, version="test", updated="2026-10-22", duplication_relevant=set())
