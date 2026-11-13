"""Curated rule import (knowledge_base/data -> PostgreSQL), run inside the throwaway test schema."""

import dataclasses
import shutil

import pytest
from sqlalchemy import func, select

from app.engine import ConfirmedItem, analyze, load_kb_from_db
from app.engine.loader import DEFAULT_KB_DIR, load_kb
from app.models import CascadeRule, Contraindication, DrugInteraction, Medication
from app.models.enums import FactorType, Severity
from scripts import import_kb_rules as ikr
from scripts.import_medicines import SOURCE as KAGGLE_SOURCE


@pytest.fixture(scope="module")
def curated():
    return ikr.load_curated()


def _id(db, name):
    return db.scalar(select(Medication.id).where(Medication.standard_name == name))


def _db_kb(db):
    return load_kb_from_db(db, version="t", updated="2026-11-04")


def test_import_makes_every_check_work_from_the_database(db, curated):
    counts = ikr.import_rules(db, curated)
    assert counts == {"medications added": 22, "interactions": 16, "class interaction rules": 0,
                      "interactions from class rules": 0, "contraindications": 8, "cascade rules": 4}

    # Existing (Kaggle/test) medications keep their row; curated brand names are added as aliases.
    ibu = db.scalar(select(Medication).where(Medication.standard_name == "Ibuprofen"))
    assert ibu.source == "test fixture"
    assert {"Brufen", "Advil"} <= set(ibu.alias_names)
    warfarin = db.scalar(select(Medication).where(Medication.standard_name == "Warfarin"))
    assert warfarin.source == ikr.CURATED_MEDICATION_SOURCE

    kb = _db_kb(db)
    result = analyze(
        [
            ConfirmedItem(1, warfarin.id, "Coumadin"),
            ConfirmedItem(2, ibu.id, "Brufen"),
            ConfirmedItem(3, _id(db, "Amlodipine"), "Norvasc"),
            ConfirmedItem(4, _id(db, "Furosemide"), "Lasix"),
            ConfirmedItem(5, _id(db, "Metformin"), "Glucophage"),
        ],
        kb,
        {"age_range": "65_plus", "kidney_function": "impaired"},
    )
    by_id = {w.rule_id: w for w in result.warnings}
    assert by_id["INT-0002"].severity == "Major"
    assert by_id["INT-0002"].matched_factors == ("age_range:65_plus",)
    assert by_id["CI-0001"].severity == "Major"  # label contraindication is only eGFR < 30
    assert by_id["CI-0001"].matched_factors == ("age_range:65_plus",)
    assert by_id["CAS-0001"].matched_factors == ("age_range:65_plus",)
    assert "CAS-0004" in by_id  # NSAID (ibuprofen) -> calcium channel blocker (amlodipine)
    assert by_id["INT-0002"].kb_version == "t"


def test_class_based_cascades_are_expanded_to_medications(db, curated):
    ikr.import_rules(db, curated)
    rule = db.scalar(select(CascadeRule).where(CascadeRule.rule_code == "CAS-0004"))
    triggers = {m.standard_name for m in rule.triggering_medications}
    downstream = {m.standard_name for m in rule.downstream_medications}
    assert {"Ibuprofen", "Naproxen"} <= triggers
    assert {"Lisinopril", "Amlodipine"} <= downstream
    assert rule.relevant_risk_factors == ["age_range:65_plus"]


def test_import_is_idempotent_and_removes_stale_rules(db, curated):
    ikr.import_rules(db, curated)
    para, ibu = _id(db, "Paracetamol"), _id(db, "Ibuprofen")
    low, high = sorted((para, ibu))
    db.add(DrugInteraction(rule_code="INT-STALE", drug_a_id=low, drug_b_id=high, description="old",
                           severity=Severity.MINOR, source="seed-unverified"))
    db.add(Contraindication(rule_code="CI-STALE", medication_id=para, factor_type=FactorType.KIDNEY_FUNCTION,
                            factor_value="impaired", description="old", severity=Severity.MINOR,
                            source="seed-unverified"))
    db.add(Contraindication(rule_code="CI-AGE-IBUPROFEN", medication_id=ibu, factor_type=FactorType.AGE_RANGE,
                            factor_value="under_18", description="label", severity=Severity.MODERATE,
                            source=KAGGLE_SOURCE))
    db.add(CascadeRule(rule_code="CAS-STALE", symptom_pattern="x", description="old", source="seed-unverified",
                       triggering_medications=[db.get(Medication, para)],
                       downstream_medications=[db.get(Medication, ibu)]))
    db.flush()

    counts = ikr.import_rules(db, curated)
    assert counts["medications added"] == 0
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(DrugInteraction)) == 16
    assert db.scalar(select(func.count()).select_from(CascadeRule)) == 4
    codes = set(db.scalars(select(Contraindication.rule_code)))
    assert "CI-STALE" not in codes
    assert "CI-AGE-IBUPROFEN" in codes  # Kaggle rules are left alone
    _db_kb(db)  # still a valid knowledge base


def test_conflicting_contraindication_is_reported(db, curated):
    db.add(Contraindication(rule_code="CI-AGE-PARA", medication_id=_id(db, "Paracetamol"),
                            factor_type=FactorType.LIVER_FUNCTION, factor_value="impaired",
                            description="other", severity=Severity.MINOR, source=KAGGLE_SOURCE))
    db.flush()
    with pytest.raises(ikr.CuratedImportError, match="already has rule CI-AGE-PARA"):
        ikr.import_rules(db, curated)


def test_existing_class_is_kept_and_noted(db, curated, capsys):
    db.scalar(select(Medication).where(Medication.standard_name == "Omeprazole")).drug_class = "Antacid"
    db.flush()
    ikr.import_rules(db, curated, duplication_relevant=_relevant(curated) | {"Antacid"})
    assert "Omeprazole: database class 'Antacid' kept" in capsys.readouterr().out


def _relevant(kb):
    return {c.name for c in kb.classes.values() if c.duplication_relevant}


def test_curated_flags_must_agree_with_config(curated):
    errors = ikr.check_curated(curated, set())
    assert any("'NSAID' duplication_relevant=true disagrees" in e for e in errors)
    assert ikr.check_curated(curated, _relevant(curated)) == []


@pytest.fixture
def kb_copy(tmp_path):
    folder = tmp_path / "kb"
    shutil.copytree(DEFAULT_KB_DIR, folder)
    return folder


def test_multi_class_medication_and_duplicate_pair_are_rejected(kb_copy, curated):
    meds = kb_copy / "medications.csv"
    meds.write_text(meds.read_text().replace("Warfarin,Anticoagulant,", "Warfarin,Anticoagulant;Statin,"))
    inter = kb_copy / "interactions.csv"
    inter.write_text(inter.read_text() + 'INT-9999,aspirin,warfarin,Minor,"dup",,seed-unverified\n')
    errors = ikr.check_curated(load_kb(kb_copy), _relevant(curated))
    assert any("Warfarin has 2 classes" in e for e in errors)
    assert any("has 2 rules" in e for e in errors)


def test_import_refuses_invalid_curated_data(db, curated):
    with pytest.raises(ikr.CuratedImportError, match="disagrees"):
        ikr.import_rules(db, curated, duplication_relevant=set())


def test_import_refuses_version_mismatch(db, kb_copy):
    (kb_copy / "kb_meta.json").write_text('{"version": "9.9.9", "updated": "2026-11-04"}')
    with pytest.raises(ikr.CuratedImportError, match="kb_meta.json says 9.9.9"):
        ikr.import_rules(db, load_kb(kb_copy))


def test_main_reports_invalid_files(kb_copy, capsys):
    (kb_copy / "interactions.csv").write_text("rule_id\n")
    assert ikr.main(["--data-dir", str(kb_copy)]) == 1
    assert "interactions.csv" in capsys.readouterr().out


CLASS_RULE = "INT-0100,warfarin,,Major,NSAIDs with warfarin raise bleeding risk.,age_range:65_plus,src,,NSAID\n"


def _add_db_nsaids(db):
    """Medications only the database has (as after the Kaggle import), including a combination."""
    db.add_all([
        Medication(standard_name="Celecoxib", drug_class="NSAID", source=KAGGLE_SOURCE,
                   medication_info={"active_ingredients": ["Celecoxib"]}),
        Medication(standard_name="Ibuprofen + Pseudoephedrine", drug_class="NSAID", source=KAGGLE_SOURCE,
                   medication_info={"active_ingredients": ["Ibuprofen", "Pseudoephedrine"]}),
    ])
    db.flush()


def test_class_rule_is_expanded_against_database_medications(db, kb_copy):
    _add_db_nsaids(db)
    with (kb_copy / "interactions.csv").open("a", encoding="utf-8") as handle:
        handle.write(CLASS_RULE)
    kb = load_kb(kb_copy)

    counts = ikr.import_rules(db, kb)
    # Celecoxib is not in medications.csv, so only the database expansion finds it. Ibuprofen and
    # naproxen keep INT-0002 / INT-0003; the combination is covered through ibuprofen.
    assert counts["class interaction rules"] == 1
    assert counts["interactions from class rules"] == 1
    warfarin, celecoxib = _id(db, "Warfarin"), _id(db, "Celecoxib")
    code = f"INT-0100/{min(warfarin, celecoxib)}-{max(warfarin, celecoxib)}"
    assert set(db.scalars(select(DrugInteraction.rule_code).where(DrugInteraction.rule_code.like("INT-0100%")))) == {code}

    db_kb = _db_kb(db)
    result = analyze([ConfirmedItem(1, celecoxib, "Celebrex"), ConfirmedItem(2, warfarin, "Coumadin")], db_kb)
    (warning,) = [w for w in result.warnings if w.category == "DDI"]
    assert (warning.rule_id, warning.details) == (code, {"class_rule": "INT-0100"})

    combo = _id(db, "Ibuprofen + Pseudoephedrine")
    result = analyze([ConfirmedItem(1, combo, "Arinac"), ConfirmedItem(2, warfarin, "Coumadin")], db_kb)
    assert [w.rule_id for w in result.warnings if w.category == "DDI"] == ["INT-0002"]

    # Idempotent, and the generated rows disappear with their class rule.
    assert ikr.import_rules(db, kb)["interactions from class rules"] == 1
    ikr.import_rules(db, ikr.load_curated())
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(DrugInteraction)) == 16


def test_class_rule_without_members_is_noted(db, kb_copy, capsys):
    with (kb_copy / "interactions.csv").open("a", encoding="utf-8") as handle:
        handle.write("INT-0101,warfarin,,Minor,x,,src,,Biguanide\n")
        handle.write("INT-0102,,,Minor,x,,src,Biguanide,Biguanide\n")
    ikr.import_rules(db, load_kb(kb_copy))
    out = capsys.readouterr().out
    assert "INT-0102: class rule matches no medication pair" in out
    assert "INT-0101: class rule" not in out


def test_overlap_found_only_in_the_database_is_refused(db, kb_copy):
    _add_db_nsaids(db)
    with (kb_copy / "interactions.csv").open("a", encoding="utf-8") as handle:
        handle.write(CLASS_RULE)
    kb = load_kb(kb_copy)
    (rule,) = kb.class_interactions
    kb = dataclasses.replace(kb, class_interactions=(rule, dataclasses.replace(rule, rule_id="INT-0199")))
    with pytest.raises(ikr.CuratedImportError, match="INT-0100 and INT-0199 both cover"):
        ikr.import_rules(db, kb)
