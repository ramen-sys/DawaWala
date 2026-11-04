"""Schema matches SRS Table 5.1, and the Kaggle import loads only the required data."""

import pandas as pd
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    CascadeRule,
    Contraindication,
    DrugInteraction,
    Medication,
    MedicationList,
    PrescriptionImage,
    RiskFactor,
    User,
    cascade_rule_triggers,
)
from app.models.enums import FactorType, Severity, UserRole
from app.models.medication_list import random_file_reference
from scripts import import_medicines as im
from tests.conftest import TEST_SCHEMA, unique_email

# Table 5.1 entity -> columns. Additions beyond the key attributes, and why:
# * users.failed_login_attempts / locked_until - account.lock_state (Appendix A.2)
# * analysis_results.freshness                 - analysis.freshness (Appendix A.2)
# * rule_code / source on KB rule tables       - rule identifier (QA-EXP-04) and data source (Section 5.3)
# * medications.source / external_code         - data source (5.3) and optional external code (5.4)
# Helper tables: medication_aliases (Medication "Aliases/brand names"), cascade_rule_triggers /
# cascade_rule_downstream (Cascade Rule "Triggering / Downstream medication(s)") and auth_events (SEC-10).
SRS_TABLES = {
    "users": {"id", "name", "email", "password_hash", "role", "created_at",
              "failed_login_attempts", "locked_until"},
    "medication_lists": {"id", "user_id", "source", "confirmation_status", "created_at"},
    "medication_list_items": {"id", "list_id", "medication_id", "raw_text", "match_score", "confirmation_flag"},
    "medications": {"id", "standard_name", "drug_class", "medication_info", "source", "external_code"},
    "medication_aliases": {"id", "medication_id", "alias"},
    "prescription_images": {"id", "list_id", "file_reference", "uploaded_at", "ocr_status"},
    "ocr_extraction_results": {"id", "image_id", "raw_text", "candidates", "confidence"},
    "drug_interactions": {"id", "rule_code", "drug_a_id", "drug_b_id", "description", "severity",
                          "relevant_risk_factors", "source"},
    "contraindications": {"id", "rule_code", "medication_id", "factor_type", "factor_value", "description",
                          "severity", "source"},
    "cascade_rules": {"id", "rule_code", "symptom_pattern", "description", "source"},
    "cascade_rule_triggers": {"rule_id", "medication_id"},
    "cascade_rule_downstream": {"rule_id", "medication_id"},
    "risk_factors": {"id", "user_id", "list_id", "factor_type", "factor_value"},
    "analysis_results": {"id", "list_id", "timestamp", "kb_version", "freshness"},
    "warnings": {"id", "analysis_id", "category", "rule_reference", "related_medications", "score",
                 "score_factors", "explanation"},
    "auth_events": {"id", "user_id", "event_type", "ip_address", "created_at"},
}


def test_schema_matches_srs_table_5_1(engine):
    insp = inspect(engine)
    tables = set(insp.get_table_names(schema=TEST_SCHEMA))
    assert tables == set(SRS_TABLES)
    for table, columns in SRS_TABLES.items():
        actual = {c["name"] for c in insp.get_columns(table, schema=TEST_SCHEMA)}
        assert actual == columns, table


def test_enums_match_srs():
    assert {r.value for r in UserRole} == {"user", "admin"}
    assert {s.value for s in Severity} == {"minor", "moderate", "major", "contraindicated"}


def test_trigram_indexes_exist(engine):
    insp = inspect(engine)
    for table, index in [("medications", "ix_medications_standard_name_trgm"),
                         ("medication_aliases", "ix_medication_aliases_alias_trgm")]:
        assert index in {i["name"] for i in insp.get_indexes(table, schema=TEST_SCHEMA)}


def _paracetamol(db) -> Medication:
    return db.scalar(select(Medication).where(Medication.standard_name == "Paracetamol"))


def _assert_rejected(db, obj) -> None:
    db.add(obj)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


@pytest.mark.parametrize("factor_type, factor_value", [
    (FactorType.AGE_RANGE, "under18"),        # typo
    (FactorType.KIDNEY_FUNCTION, "under_18"),  # value of another factor type
])
def test_contraindication_rejects_invalid_factor_value(db, factor_type, factor_value):
    _assert_rejected(db, Contraindication(
        rule_code=f"CI-TEST-{factor_value}", medication_id=_paracetamol(db).id, factor_type=factor_type,
        factor_value=factor_value, description="x", severity=Severity.MINOR, source="test",
    ))


def test_risk_factor_rejects_invalid_factor_value(db):
    user = User(name="RF", email=unique_email("rf"), password_hash="x")
    med_list = MedicationList(user=user)
    db.add_all([user, med_list])
    db.flush()
    _assert_rejected(db, RiskFactor(user_id=user.id, list_id=med_list.id,
                                    factor_type=FactorType.LIVER_FUNCTION, factor_value="bad"))


def test_interaction_rejects_unknown_risk_factor(db):
    ids = sorted(db.scalars(select(Medication.id).limit(2)).all())
    _assert_rejected(db, DrugInteraction(
        rule_code="DDI-TEST", drug_a_id=ids[0], drug_b_id=ids[1], description="x", severity=Severity.MAJOR,
        relevant_risk_factors=["age_range", "kidney_fuction"], source="test",
    ))


def test_cascade_rule_uses_join_tables_with_foreign_keys(db):
    para = _paracetamol(db)
    ibu = db.scalar(select(Medication).where(Medication.standard_name == "Ibuprofen"))
    rule = CascadeRule(rule_code="CAS-TEST", symptom_pattern="Stomach pain", description="x", source="test",
                       triggering_medications=[ibu], downstream_medications=[para])
    db.add(rule)
    db.flush()
    db.refresh(rule)
    assert [m.standard_name for m in rule.triggering_medications] == ["Ibuprofen"]
    assert [m.standard_name for m in rule.downstream_medications] == ["Paracetamol"]

    # A medication ID that does not exist is refused by the foreign key.
    with pytest.raises(IntegrityError):
        db.execute(cascade_rule_triggers.insert().values(rule_id=rule.id, medication_id=999_999))
    db.rollback()


def test_prescription_image_gets_random_file_reference(db):
    user = User(name="Img", email=unique_email("img"), password_hash="x")
    med_list = MedicationList(user=user)
    a, b = PrescriptionImage(medication_list=med_list), PrescriptionImage(medication_list=med_list)
    db.add_all([user, med_list, a, b])
    db.flush()
    assert len(a.file_reference) == 32 and a.file_reference != b.file_reference
    assert random_file_reference("PNG").endswith(".png")
    db.rollback()


# ---------- Kaggle dataset import ----------

@pytest.fixture(scope="module")
def dataset():
    rows, skipped = im.load_dataset()
    medications, min_ages = im.build_records(rows)
    return rows, skipped, medications, {m["standard_name"]: m for m in medications}, min_ages


def test_every_dataset_product_is_mapped_or_explicitly_skipped(dataset):
    rows, skipped, *_ = dataset
    raw = pd.read_csv(im.DATASET_CSV)
    assert set(raw["Drug Name"].str.strip()) == set(rows["Drug Name"]) | set(skipped["Drug Name"])
    assert set(skipped["Drug Name"]) == {"Coughnil", "Aloe Vera Gel"}


def test_only_required_columns_are_read(dataset):
    rows, *_ = dataset
    assert not {"Manufacturer", "Strength", "Form", "Available In", "Prescription Required", "Price"} & set(rows)


def test_brands_are_merged_under_one_generic(dataset):
    *_, by_name, _ = dataset
    para = by_name["Paracetamol"]
    assert para["aliases"] == ["Calpol", "Disprol", "Panadol", "Panadol Extend"]
    assert para["drug_class"] == "Analgesic / antipyretic"
    assert para["medication_info"]["active_ingredients"] == ["Paracetamol"]
    assert by_name["Cetirizine"]["aliases"] == ["Histac", "Rigix", "Zyrtec"]
    assert by_name["Omeprazole"]["aliases"] == ["Losec", "Risek"]
    # A medication whose standard name equals the product name is not repeated as an alias.
    assert by_name["Naproxen"]["aliases"] == []


def test_medication_info_holds_only_srs_relevant_fields(dataset):
    *_, by_name, _ = dataset
    assert by_name["Clonazepam"]["source"] == im.SOURCE
    info = by_name["Clonazepam"]["medication_info"]
    assert set(info) == {"active_ingredients", "indications", "side_effects", "min_age_years"}
    assert info["indications"] == ["Anxiety", "Seizures"]
    assert info["side_effects"] == ["Drowsiness", "Dependency risk"]
    assert info["min_age_years"] == 18


@pytest.mark.parametrize(
    "value, expected",
    [("12+", 12), ("All ages", 0), ("0+", 0), (" 18+ ", 18), (float("nan"), None)],
)
def test_parse_min_age(value, expected):
    assert im.parse_min_age(value) == expected


def test_lowest_age_is_used_when_products_differ(dataset):
    *_, min_ages = dataset
    assert min_ages["Ibuprofen"] == 0  # Brufen 12+, Ibuprofen (Children) 0+
    assert min_ages["Erythromycin"] == 0  # one Erythrocin row says All ages, the other 6+


def test_age_rule_code_is_stable_and_short():
    assert im.age_rule_code("Clonazepam") == "CI-AGE-CLONAZEPAM"
    assert im.age_rule_code("Ibuprofen + Pseudoephedrine") == "CI-AGE-IBUPROFEN-PSEUDOEPHEDRINE"
    assert len(im.age_rule_code("X" * 200)) == 50


def test_import_into_db_is_idempotent(session_factory, dataset):
    *_, medications, _, min_ages = dataset
    with session_factory() as db:
        first = im.import_into_db(db, medications, min_ages)
        second = im.import_into_db(db, medications, min_ages)
        assert first == second == (69, 51)

        meds = db.scalars(select(Medication).where(Medication.standard_name.in_([m["standard_name"] for m in medications]))).all()
        assert len(meds) == 69

        clonazepam = db.scalar(select(Medication).where(Medication.standard_name == "Clonazepam"))
        assert clonazepam.alias_names == ["Rivotril"]
        assert clonazepam.source == im.SOURCE
        ci = db.scalars(select(Contraindication).where(Contraindication.medication_id == clonazepam.id)).all()
        assert [(c.rule_code, c.factor_type, c.factor_value, c.severity) for c in ci] == [
            ("CI-AGE-CLONAZEPAM", FactorType.AGE_RANGE, "under_18", Severity.MAJOR)
        ]
        assert ci[0].source == im.SOURCE
        assert "aged 18 and over" in ci[0].description

        # Re-import replaces aliases instead of duplicating them.
        para = db.scalar(select(Medication).where(Medication.standard_name == "Paracetamol"))
        db.refresh(para)
        assert para.alias_names == ["Calpol", "Disprol", "Panadol", "Panadol Extend"]

        amoxil = db.scalar(select(Medication).where(Medication.standard_name == "Amoxicillin"))
        assert db.scalar(select(Contraindication).where(Contraindication.medication_id == amoxil.id)) is None


def test_imported_brand_names_resolve_in_manual_entry(client, make_user, session_factory, dataset):
    *_, medications, _, min_ages = dataset
    with session_factory() as db:
        im.import_into_db(db, medications, min_ages)
    _, h = make_user()
    r = client.post("/api/v1/medication-lists", json={"names": ["Arinac Forte", "Rivotril 0.5mg", "Coughnil"]},
                    headers=h)
    names = [i["medication"]["standard_name"] if i["medication"] else None for i in r.json()["items"]]
    assert names == ["Ibuprofen + Pseudoephedrine", "Clonazepam", None]
