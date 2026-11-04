# Knowledge base

The safety engine is rule-based (BR-05). At runtime `load_kb_from_db()` reads the PostgreSQL tables `medications`, `drug_interactions`, `contraindications` and `cascade_rules`. Adding a row adds a rule; the detectors do not change.

The CSV files in this folder are only the source for the one-time import. The engine does not read them. `tests/engine/fixtures/kb/` is a small frozen set used only by the detector unit tests.

## Database files

| File | What it is |
|---|---|
| `data/pakistan_medicines_dataset.csv` | Unmodified copy of the Kaggle [Pakistan Medicines Dataset](https://www.kaggle.com/datasets/muhammadabdullah222/pakistan-medicines-dataset) (version 3, 97 rows). |
| `data/brand_generic_map.csv` | Hand-curated mapping from each product name in the dataset to its standard (generic) name, drug class and active ingredients. The dataset has no generic-name column, so this mapping is required. Rows with a `skip_reason` are not imported. |

## What is imported

Only the dataset columns that the SRS (Table 5.1, Medication and Contraindication entities) needs are used:

| Dataset column | Goes to |
|---|---|
| Drug Name | `medications.aliases` (brand names) and, through the mapping, `medications.standard_name` |
| Indication | `medications.medication_info.indications` |
| Side Effects | `medications.medication_info.side_effects` |
| Age Restriction | `medications.medication_info.min_age_years`, and a `contraindications` row for `age_range:under_18` |

Manufacturer, Strength, Form, Available In, Prescription Required and Price are not used: the SRS does not store them (FR-6 discards strengths and dosage forms).

Products that share a generic name are merged into one medication (for example Panadol, Calpol, Disprol and Panadol Extend all become **Paracetamol**). When the age restriction differs between products of the same generic, the lowest age is used, because the strictest limit usually belongs to one specific strength.

Drug-drug interactions (FR-8) and prescribing cascades (FR-12) are not in this dataset. They are rows in `drug_interactions` and `cascade_rules`. Therapeutic duplicates (FR-9) come from `medications.drug_class` when that class is listed in `DUPLICATION_RELEVANT_CLASSES`.

## Import

```bash
cd backend
python -m scripts.import_medicines              # uses the committed CSV
python -m scripts.import_medicines --from-kaggle  # downloads the latest version first (needs kagglehub)
```

The import is idempotent: running it again updates existing rows instead of creating duplicates.

All knowledge-base content must be reviewed by a pharmacist or physician before any use beyond the academic prototype (SAF-09).
