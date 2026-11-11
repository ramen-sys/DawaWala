# Clinical review of the curated rules (SAF-09)

Every curated rule (interactions, contraindications, prescribing cascades) must be approved by a
pharmacist or physician before Dawawala is used beyond the academic prototype.

## Files

| File | Who edits it | What it is |
|---|---|---|
| `evidence_check.csv` | Knowledge-base curator | For each rule: evidence verdict, changes made because of the evidence, open points for the reviewer, the URLs read and a supporting quote. |
| `clinical_review.csv` | Reviewer (columns `reviewer_name` to `reviewer_comments` only) | One row per rule, showing the rule exactly as the app will use it, plus the evidence summary. |

## For the reviewer

1. Open `clinical_review.csv` in Excel or Google Sheets.
2. For each row, read `rule`, `severity`, `relevant_factors` and `description` (the text patients see).
   The `evidence_check` column summarises the evidence; full links and quotes are in `evidence_check.csv`.
3. Fill in `reviewer_name`, `reviewer_role` (e.g. Pharmacist), `review_date` (YYYY-MM-DD) and `decision`:
   * `approved`: correct as written.
   * `changes_needed`: describe the change in `reviewer_comments`.
   * `rejected`: the rule should be removed; say why in `reviewer_comments`.
4. Save as CSV (UTF-8) and return the file. Do not edit the other columns; they are regenerated.

Things to check:

* **Severity.** The app has only Minor / Moderate / Major / Contraindicated, and its kidney and liver
  factors are just "impaired" or "normal". Several labels use thresholds (e.g. metformin is
  contraindicated only below eGFR 30), so severities are set for a generic "impaired" patient.
* **Relevant factors.** Each one the patient has adds +5 to the warning score.
* **Wording.** Descriptions must be plain language and, for cascades, must say "may" or
  "sometimes", never present a diagnosis.

## For the curator

```bash
python knowledge_base/review_sheet.py           # refresh the sheet after changing a rule CSV or evidence_check.csv
python knowledge_base/review_sheet.py --check   # print status; exit code 1 until every rule is approved
```

Approvals are kept when the sheet is refreshed. If a rule changes after it was approved, the sheet
resets its decision and notes the previous one in `reviewer_comments`, so the rule is reviewed again.
Apply `changes_needed` and `rejected` decisions in `knowledge_base/data/`, then re-run
`python -m scripts.import_kb_rules` from `backend/`.
