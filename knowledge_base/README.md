# Knowledge base data

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
