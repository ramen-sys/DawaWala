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
| Drug Name | `medication_aliases.alias` (brand names) and, through the mapping, `medications.standard_name` |
| Indication | `medications.medication_info.indications` |
| Side Effects | `medications.medication_info.side_effects` |
| Age Restriction | `medications.medication_info.min_age_years`, and a `contraindications` row with `factor_type = age_range`, `factor_value = under_18` and rule code `CI-AGE-<NAME>` |

Every imported medication and contraindication has `source` set to the dataset name and version (SRS 5.3).

Manufacturer, Strength, Form, Available In, Prescription Required and Price are not used: the SRS does not store them (FR-6 discards strengths and dosage forms).

Products that share a generic name are merged into one medication (for example Panadol, Calpol, Disprol and Panadol Extend all become **Paracetamol**). When the age restriction differs between products of the same generic, the lowest age is used, because the strictest limit usually belongs to one specific strength.

Drug-drug interactions (FR-8), prescribing cascades (FR-12) and contraindications other than age are not in this dataset. They are curated by hand in the files below and imported by `scripts.import_kb_rules`.

## Curated rule files

| File | What it is |
|---|---|
| `data/medications.csv` | Medicines the rules refer to. Ones missing from the database are added. Existing ones keep their Kaggle class; only missing brand names are added. |
| `data/drug_classes.csv` | Classes used by the curated files. `duplication_relevant` must agree with `DUPLICATION_RELEVANT_CLASSES` in `backend/app/core/config.py` (the single source of truth for FR-9), or the import stops. |
| `data/interactions.csv` | FR-8 rules, one per pair of medicines. |
| `data/contraindications.csv` | FR-10 rules for kidney, liver and age conditions. |
| `data/cascades.csv` | FR-12 rules. Trigger and downstream sides may name medicines or classes; classes are expanded into every medicine of that class in the database at import time. |

Naming conventions:

* Medicine names use the database's style: `Paracetamol`, and `Levodopa + Carbidopa` for combinations.
* Class names use the database's style: `NSAID`, `Proton-pump inhibitor`, `Calcium channel blocker`.
* `relevant_factors` are `factor:value` tokens separated by `;`, e.g. `age_range:65_plus;kidney_function:impaired`. Each one the patient has adds +5 to the score (Table 5.2, max +15).
* `rule_id` becomes the database `rule_code` and is shown on every warning, so never reuse one.

## Import

```bash
cd backend
python -m scripts.import_medicines              # 1. Kaggle medicines and age rules
python -m scripts.import_kb_rules               # 2. curated rules (always after step 1)
python ../knowledge_base/check_kb.py            # 3. validate and show progress to the release targets
```

`python -m scripts.seed` runs steps 1 and 2. Use `import_medicines --from-kaggle` to download the latest dataset first (needs kagglehub), and `import_kb_rules --dry-run` to check the files without writing.

Step 2 must follow step 1 because the Kaggle import replaces the aliases of its medicines. Re-run step 2 after adding medicines to a class used by a cascade rule.

Both imports are idempotent: running them again updates existing rows instead of creating duplicates. Rules deleted from the curated files are deleted from the database; rules imported from the Kaggle dataset are never touched by step 2.

All knowledge-base content must be reviewed by a pharmacist or physician before any use beyond the academic prototype (SAF-09).
