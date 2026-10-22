<<<<<<< HEAD
# Knowledge base (Member 3)

The safety engine is rule-based (BR-05): every warning comes from a row in
these CSV files. Adding a row adds a rule; no code changes are needed
(QA-MNT-01).

> **Status:** `data/` holds a small seed KB for development. Every rule is
> marked `seed-unverified` and must be checked against a real source before
> release. No rule may be used outside the prototype until a pharmacist or
> physician has reviewed it (SAF-09).

## Checking your work

From the repository root:

```bash
python knowledge_base/check_kb.py     # validates every file, shows progress to targets
pytest                                # runs all engine tests, incl. one test per rule
```

`check_kb.py` lists **every** error at once (unknown medicine names, bad
severities, duplicate rule IDs, clashing brand names, ...), so fix a batch
and run it again.

## Files in `data/`

All files are UTF-8 CSV. Cells that hold several values use `;`.
Rule files refer to medicines by **standard name only**, never by brand.

| File | Columns | Notes |
|---|---|---|
| `kb_meta.json` | `version`, `updated` | Bump both on every change. Shown on every result (SAF-07). |
| `risk_factors.csv` | `factor`, `allowed_values` | Vocabulary from SRS A.2. `unknown` is implicit. |
| `drug_classes.csv` | `class_name`, `duplication_relevant` | `true` means two different drugs in the class raise a therapeutic-duplication warning (FR-9). |
| `medications.csv` | `medication_id`, `standard_name`, `classes`, `aliases` | Aliases are brand names. Usman's fuzzy matching uses them, so include Pakistani brands. |
| `interactions.csv` | `rule_id`, `drug_a`, `drug_b`, `severity`, `description`, `relevant_factors`, `source` | FR-8. Pair order does not matter. |
| `contraindications.csv` | `rule_id`, `medication`, `factor`, `value`, `severity`, `description`, `relevant_factors`, `source` | FR-10. `factor`/`value` is the condition, e.g. `kidney_function` / `impaired`. |
| `cascades.csv` | `rule_id`, `trigger_medications`, `trigger_classes`, `symptom_pattern`, `downstream_medications`, `downstream_classes`, `description`, `relevant_factors`, `source` | FR-12. Each side needs at least one medicine or class. Prefer classes so new medicines are covered automatically. |

**Severity** is one of `Minor`, `Moderate`, `Major`, `Contraindicated`
(the SRS 5.5 scoring scale).

**relevant_factors** are written `factor:value`, e.g.
`age_range:65_plus;kidney_function:impaired`. Scoring adds +5 for each one
the patient has. For a contraindication, do not repeat its own condition
here; the loader rejects that because it would be counted twice.

**description** is shown to users, so keep it plain (grade 9 or lower,
QA-EXP-03) and never tell the user to start, stop or change a medicine
(SAF-06).

**Rule IDs**: `INT-0001`, `CI-0001`, `CAS-0001`; never reuse an ID.

## Curation workflow

1. Put downloaded source files in `raw/` (git-ignored, because some sources
   restrict redistribution).
2. Clean and map them to the formats above with pandas, writing to `data/`.
3. Record every source and its licence in `SOURCES.md`, and put a short
   source tag in each row's `source` column (SRS 5.3).
4. Run `check_kb.py` and `pytest`, then commit with the requirement ID,
   e.g. `FR-8: add 120 cardiovascular interactions`.

Release 1.0 targets (QA-COR-04): 300 medications, 1,000 interactions,
100 contraindications, 20 cascade rules.

`tests/engine/fixtures/kb/` is a frozen copy of the seed KB used by the
behaviour tests (QA-TST-02). Do not edit it when curating; edit `data/`.
=======
# Knowledge base data

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

Manufacturer, Strength, Form, Available In, Prescription Required and Price are not used: the SRS
does not store them (FR-6 discards strengths and dosage forms).

Products that share a generic name are merged into one medication (for example Panadol, Calpol, Disprol and
Panadol Extend all become **Paracetamol**). When the age restriction differs between products of the same
generic, the lowest age is used, because the strictest limit usually belongs to one specific strength.

## Import

```bash
cd backend
python -m scripts.import_medicines              # uses the committed CSV
python -m scripts.import_medicines --from-kaggle  # downloads the latest version first (needs kagglehub)
```

The import is idempotent: running it again updates existing rows instead of creating duplicates.

> The dataset does not contain drug-drug interactions or prescribing-cascade rules; those are added separately.
> All knowledge-base content must be reviewed by a pharmacist or physician before any use beyond the
> academic prototype (SAF-09).
>>>>>>> ad9157eef12a848d2b71f01802de4c4da9f1313a
