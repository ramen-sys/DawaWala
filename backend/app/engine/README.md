# Safety engine (Member 3): FR-8, FR-9, FR-10, FR-12

The engine takes a **confirmed** medication list and returns warnings. The
detectors themselves do not query PostgreSQL: the caller loads the knowledge
base from the database once, then passes it in. Scoring (FR-11) and
explanations (FR-13) happen after it.

## How to call it (for Rameen: API layer)

```python
from app.engine import ConfirmedItem, analyze, load_kb_from_db

kb = load_kb_from_db(db)   # once at start-up; raises KBValidationError if a row is invalid

items = [
    ConfirmedItem(item_id=101, medication_id=8,  entered_text="Norvasc"),
    ConfirmedItem(item_id=102, medication_id=10, entered_text="Lasix"),
    ConfirmedItem(item_id=103, medication_id=None, entered_text="Vitamin D drops"),  # kept as unrecognised
]
result = analyze(items, kb, {"age_range": "65_plus", "kidney_function": "unknown"})
payload = result.to_dict()   # JSON-ready
```

* Only call `analyze()` on a list whose status is `confirmed` (BR-01, SAF-01).
* `risk_factors` keys and values are the SRS vocabulary enforced when the database rows are loaded.
  Missing keys count as `unknown`. An unknown key or value raises `ValueError`,
  which the API should return as HTTP 422.
* The same list, factors and KB version always give identical output (QA-REL-01).

## What comes back (for Mustafa: scoring and explanations)

`result.warnings` is a list of `SafetyWarning`:

| Field | Meaning |
|---|---|
| `category` | `contraindication`, `DDI`, `cascade` or `duplicate` (SRS A.2) |
| `rule_id` | e.g. `INT-0001`, `CI-0001`, `CAS-0001`, `DUP-EXACT`, `DUP-CLASS:NSAID` (QA-EXP-04) |
| `medication_ids`, `medication_names` | The medicines involved |
| `severity` | `Minor`/`Moderate`/`Major`/`Contraindicated` for DDI and contraindication; `None` for duplicate and cascade |
| `description` | Plain-language reason from the KB, for your explanation text |
| `relevant_factors` | Factors the rule lists as relevant, e.g. `["age_range:65_plus"]` |
| `matched_factors` | The subset this patient actually has: **+5 each, max +15** in Table 5.2 |
| `details` | Duplicates: `kind` = `exact` (30 pts) or `therapeutic` (15 pts), plus `entered_as` or `drug_class`. Cascades: `trigger_names`, `symptom_pattern`, `downstream_names`. Contraindications: `condition`. |
| `kb_version` | KB version that produced the warning |

Also returned:

* `result.not_assessed`: contraindication checks skipped because a factor is
  unknown, with `missing_factor`. Show under "Not assessed" (FR-10).
* `result.not_analysed`: items the engine could not check. Show under
  "Not analysed" (FR-15, SAF-03).
* `result.kb_version`, `result.kb_updated`: for the results screen (SAF-07).

Warnings come grouped in the FR-11 tie-break order (contraindication, DDI,
cascade, duplicate). Re-sort by score after scoring.

Cascade warnings are always *possible* cascades: the engine cannot know
which medicine came first, so explanations must not word them as a diagnosis.

## Tests

From the repository root: `pytest --cov=app.engine --cov-report=term-missing`
(100% statement coverage required, QA-MNT-04).
