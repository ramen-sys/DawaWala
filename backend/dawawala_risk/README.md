# dawawala_risk — risk-priority scoring (FR-11) and explanations (FR-13)

Pure Python 3.10+, standard library only. Rules and weights follow SRS
Section 5.5; every number lives in `dawawala_risk/scoring_config.json`
(QA-MNT-02). Set `DAWAWALA_SCORING_CONFIG=/path/to/file.json` to override.

## Run the tests

    python -m unittest discover -s tests -t .      # or: pytest
    python run_coverage.py                         # stdlib coverage, needs 100%

## Use from the backend (FastAPI / Django REST)

    from dawawala_risk import analyse_payload
    result = analyse_payload(payload)              # dict, JSON-serialisable

### Input (Member 3 -> this module)

    {
      "warnings": [{
        "category": "interaction | contraindication | cascade | duplicate",
        "medicines": ["Warfarin", "Aspirin"],
        "rule_id": "DDI-0012",            # required (QA-EXP-04)
        "kb_version": "KB-1.0.0",         # required (QA-EXP-04)
        "severity": "minor|moderate|major|contraindicated",
                                          # required for interaction/contra
        "relevant_factors": ["age_65_plus", "kidney_impaired",
                             "liver_impaired"],      # what the KB rule lists
        "duplicate_kind": "exact | therapeutic",     # duplicate only
        "description": "optional KB text",
        "condition": "contraindication: e.g. severe kidney problems",
        "trigger": "cascade: triggering medicine",
        "symptom_pattern": "cascade: new-symptom pattern",
        "downstream": "cascade: downstream medicine"
      }],
      "patient_factors": {                # optional, all default "unknown"
        "age_range": "under_18 | 18_64 | 65_plus | unknown",
        "kidney_function": "normal | impaired | unknown",
        "liver_function": "normal | impaired | unknown"
      }
    }

### Output (this module -> frontend), already sorted

    {
      "warnings": [{
        "category": "interaction", "medicines": [...], "rule_id": "...",
        "kb_version": "...", "severity": "major",
        "score": 60, "raw_total": 60, "capped": false, "band": "High",
        "factors": [{"code": "severity_major",
                     "label": "Rule severity (interaction): Major",
                     "points": 50}, ...],   # always sums to raw_total
        "explanation": "We found a possible interaction ..."
      }],
      "band_counts": {"Low": 0, "Moderate": 1, "High": 1, "Critical": 0}
    }

Frontend rules (QA-EXP-02, SAF-05): always render `factors` next to `score`;
show `band` as text plus icon, not colour alone. If `capped` is true, show
`raw_total` so the items visibly add up.

## Safety behaviour worth knowing

* An unknown severity raises an error; it is never silently scored as 0.
* KB `description` text is added to an explanation only if it fits the
  150-word limit and contains no start/stop/change-a-medicine wording;
  otherwise it is left out and noted in `explanation_notes`.
* If an explanation would exceed 150 words or contain forbidden wording
  (for example from a medicine name) the call raises instead of truncating.
* Explanation text is in `templates.py` so it can be reviewed in one place
  (SAF-06).
