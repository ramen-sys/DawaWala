"""Schema matches SRS Table 5.1, and the Kaggle import loads only the required data."""

import pandas as pd
import pytest
from sqlalchemy import inspect, select

from app.models import Contraindication, Medication
from scripts import import_medicines as im
from tests.conftest import TEST_SCHEMA

# Table 5.1 entity -> key attributes (plus account.lock_state / analysis.freshness from Appendix A.2).
SRS_TABLES = {
    "users": {"id", "name", "email", "password_hash", "role", "created_at",
              "failed_login_attempts", "locked_until"},
    "medication_lists": {"id", "user_id", "source", "confirmation_status", "created_at"},
    "medication_list_items": {"id", "list_id", "medication_id", "raw_text", "match_score", "confirmation_flag"},
    "medications": {"id", "standard_name", "aliases", "drug_class", "medication_info"},
    "prescription_images": {"id", "list_id", "file_reference", "uploaded_at", "ocr_status"},
    "ocr_extraction_results": {"id", "image_id", "raw_text", "candidates", "confidence"},
    "drug_interactions": {"id", "drug_a_id", "drug_b_id", "description", "severity", "relevant_risk_factors"},
    "contraindications": {"id", "medication_id", "patient_condition", "description", "severity"},
    "cascade_rules": {"id", "triggering_medications", "symptom_pattern", "downstream_medications", "description"},
    "risk_factors": {"id", "user_id", "list_id", "factor_type", "factor_value"},
    "analysis_results": {"id", "list_id", "timestamp", "kb_version", "freshness"},
    "warnings": {"id", "analysis_id", "category", "rule_reference", "related_medications", "score",
                 "score_factors", "explanation"},
}


def test_schema_matches_srs_table_5_1(engine):
    insp = inspect(engine)
    tables = set(insp.get_table_names(schema=TEST_SCHEMA))
    assert tables == set(SRS_TABLES)
    for table, columns in SRS_TABLES.items():
        actual = {c["name"] for c in insp.get_columns(table, schema=TEST_SCHEMA)}
        assert actual == columns, table


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
    info = by_name["Clonazepam"]["medication_info"]
    assert set(info) == {"active_ingredients", "indications", "side_effects", "min_age_years", "source"}
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


def test_import_into_db_is_idempotent(session_factory, dataset):
    *_, medications, _, min_ages = dataset
    with session_factory() as db:
        first = im.import_into_db(db, medications, min_ages)
        second = im.import_into_db(db, medications, min_ages)
        assert first == second == (69, 51)

        meds = db.scalars(select(Medication).where(Medication.standard_name.in_([m["standard_name"] for m in medications]))).all()
        assert len(meds) == 69

        clonazepam = db.scalar(select(Medication).where(Medication.standard_name == "Clonazepam"))
        assert clonazepam.aliases == ["Rivotril"]
        ci = db.scalars(select(Contraindication).where(Contraindication.medication_id == clonazepam.id)).all()
        assert [(c.patient_condition, c.severity.value) for c in ci] == [("age_range:under_18", "major")]
        assert "aged 18 and over" in ci[0].description

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
