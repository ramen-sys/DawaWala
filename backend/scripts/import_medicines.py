"""Import the Kaggle "Pakistan Medicines Dataset" into the knowledge base (medications + age contraindications).

Run from backend/:  python -m scripts.import_medicines [--from-kaggle] [--dry-run]
See knowledge_base/README.md for which columns are used and why.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Contraindication, Medication
from app.models.enums import FactorType, Severity

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "knowledge_base" / "data"
DATASET_CSV = DATA_DIR / "pakistan_medicines_dataset.csv"
MAPPING_CSV = DATA_DIR / "brand_generic_map.csv"
KAGGLE_REF = "muhammadabdullah222/pakistan-medicines-dataset"
SOURCE = "Kaggle: Pakistan Medicines Dataset (muhammadabdullah222), version 3"

USED_COLUMNS = ["Drug Name", "Indication", "Side Effects", "Age Restriction"]
UNDER_18 = f"{FactorType.AGE_RANGE.value}:under_18"


def download_from_kaggle() -> None:
    import kagglehub

    folder = Path(kagglehub.dataset_download(KAGGLE_REF))
    shutil.copyfile(next(folder.glob("*.csv")), DATASET_CSV)
    print(f"Downloaded latest dataset to {DATASET_CSV}")


def parse_min_age(value) -> int | None:
    """'12+' -> 12, 'All ages' / '0+' -> 0, missing -> None."""
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in {"all ages", "all"}:
        return 0
    match = re.fullmatch(r"(\d+)\s*\+", text)
    if not match:
        raise ValueError(f"Unrecognised age restriction: {value!r}")
    return int(match.group(1))


def split_terms(values: pd.Series) -> list[str]:
    """Split comma-separated free text into unique terms, keeping first-seen order."""
    seen: dict[str, str] = {}
    for value in values.dropna():
        for term in str(value).split(","):
            term = re.sub(r"\s+etc\.?$", "", term.strip(), flags=re.IGNORECASE).strip()
            if term and term.lower() not in seen:
                seen[term.lower()] = term[0].upper() + term[1:]
    return list(seen.values())


def load_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(DATASET_CSV, usecols=USED_COLUMNS)
    df["Drug Name"] = df["Drug Name"].str.strip()
    df["min_age"] = df["Age Restriction"].map(parse_min_age)

    mapping = pd.read_csv(MAPPING_CSV, dtype=str).fillna("")
    mapping["drug_name"] = mapping["drug_name"].str.strip()

    unmapped = sorted(set(df["Drug Name"]) - set(mapping["drug_name"]))
    if unmapped:
        sys.exit(f"These dataset products have no row in {MAPPING_CSV.name}: {unmapped}")

    merged = df.merge(mapping, left_on="Drug Name", right_on="drug_name", how="left")
    skipped = merged[merged["skip_reason"] != ""][["Drug Name", "skip_reason"]].drop_duplicates()
    return merged[merged["skip_reason"] == ""], skipped


def build_records(rows: pd.DataFrame) -> tuple[list[dict], dict[str, int | None]]:
    medications, min_ages = [], {}
    for standard_name, group in rows.groupby("standard_name", sort=True):
        brands = sorted({b for b in group["Drug Name"] if b.lower() != standard_name.lower()}, key=str.lower)
        ages = group["min_age"].dropna()
        min_age = int(ages.min()) if not ages.empty else None
        min_ages[standard_name] = min_age
        medications.append(
            {
                "standard_name": standard_name,
                "aliases": brands,
                "drug_class": group["drug_class"].iloc[0],
                "medication_info": {
                    "active_ingredients": group["active_ingredients"].iloc[0].split(";"),
                    "indications": split_terms(group["Indication"]),
                    "side_effects": split_terms(group["Side Effects"]),
                    "min_age_years": min_age,
                    "source": SOURCE,
                },
            }
        )
    return medications, min_ages


def age_severity(min_age: int) -> Severity:
    if min_age >= 18:
        return Severity.MAJOR
    if min_age >= 12:
        return Severity.MODERATE
    return Severity.MINOR


def age_description(min_age: int) -> str:
    return (
        f"The product label limits this medicine to people aged {min_age} and over. "
        "If the patient is younger, please check with a doctor or pharmacist before use. "
        f"Source: {SOURCE}."
    )


def import_into_db(db: Session, medications: list[dict], min_ages: dict[str, int | None]) -> tuple[int, int]:
    stmt = insert(Medication).values(medications)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Medication.standard_name],
        set_={
            "aliases": stmt.excluded.aliases,
            "drug_class": stmt.excluded.drug_class,
            "medication_info": stmt.excluded.medication_info,
        },
    ).returning(Medication.id, Medication.standard_name)
    ids = {name: med_id for med_id, name in db.execute(stmt).all()}

    restricted = {name: age for name, age in min_ages.items() if age}
    if restricted:
        ci = insert(Contraindication).values(
            [
                {
                    "medication_id": ids[name],
                    "patient_condition": UNDER_18,
                    "description": age_description(age),
                    "severity": age_severity(age),
                }
                for name, age in restricted.items()
            ]
        )
        ci = ci.on_conflict_do_update(
            constraint="uq_contraindications_med_condition",
            set_={"description": ci.excluded.description, "severity": ci.excluded.severity},
        )
        db.execute(ci)

    unrestricted_ids = [ids[name] for name in min_ages if name not in restricted]
    if unrestricted_ids:
        db.execute(
            delete(Contraindication).where(
                Contraindication.medication_id.in_(unrestricted_ids),
                Contraindication.patient_condition == UNDER_18,
            )
        )
    db.commit()
    return len(ids), len(restricted)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-kaggle", action="store_true", help="download the latest dataset first")
    parser.add_argument("--dry-run", action="store_true", help="print what would be imported, do not write")
    args = parser.parse_args()

    if args.from_kaggle:
        download_from_kaggle()

    rows, skipped = load_dataset()
    medications, min_ages = build_records(rows)
    print(f"Dataset products used: {rows['Drug Name'].nunique()} -> {len(medications)} standard medications")
    for _, row in skipped.iterrows():
        print(f"  skipped {row['Drug Name']!r}: {row['skip_reason']}")

    if args.dry_run:
        for med in medications:
            print(f"  {med['standard_name']:<45} {med['drug_class']:<28} aliases={med['aliases']} "
                  f"min_age={med['medication_info']['min_age_years']}")
        return

    with SessionLocal() as db:
        n_meds, n_ci = import_into_db(db, medications, min_ages)
        total = db.scalar(select(Medication.id).order_by(Medication.id.desc()).limit(1))
    print(f"Upserted {n_meds} medications and {n_ci} age contraindications (last medication id {total}).")


if __name__ == "__main__":
    main()
