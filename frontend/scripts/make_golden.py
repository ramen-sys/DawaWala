"""Generate src/mock/golden.json from the real Python scoring module.

Run from the frontend folder:  python scripts/make_golden.py ../dawawala-risk
The JS mock engine (src/mock/engine.js) must match this output exactly.
"""
import json
import sys
from pathlib import Path

risk_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "../dawawala-risk")
sys.path.insert(0, str(risk_dir.resolve()))

from dawawala_risk import analyse_payload  # noqa: E402

KB = "KB-1.0.0"


def w(category, medicines, rule, **kw):
    return {"category": category, "medicines": medicines, "rule_id": rule,
            "kb_version": KB, **kw}


ALL = ["age_65_plus", "kidney_impaired", "liver_impaired"]
old = {"age_range": "65_plus", "kidney_function": "impaired",
       "liver_function": "impaired"}
long_desc = " ".join(f"Sentence number {i} is here." for i in range(60))

cases = {
    "mixed_with_patient": {
        "warnings": [
            w("interaction", ["Warfarin", "Aspirin"], "DDI-0012",
              severity="major", relevant_factors=["age_65_plus",
                                                   "kidney_impaired"],
              description="Both medicines can raise the risk of bleeding."),
            w("contraindication", ["Metformin"], "CI-0044",
              severity="contraindicated", relevant_factors=["kidney_impaired"],
              condition="severe kidney problems"),
            w("duplicate", ["Paracetamol"], "DUP-001"),
            w("duplicate", ["Ibuprofen", "Naproxen"], "TD-007",
              duplicate_kind="therapeutic"),
            w("cascade", ["Amlodipine", "Furosemide"], "CAS-003",
              trigger="Amlodipine", symptom_pattern="ankle swelling",
              downstream="Furosemide"),
        ],
        "patient_factors": {"age_range": "65_plus",
                            "kidney_function": "impaired"},
    },
    "no_patient_info": {
        "warnings": [
            w("interaction", ["Warfarin", "Aspirin"], "DDI-1",
              severity="major", relevant_factors=ALL),
            w("interaction", ["Digoxin", "Amiodarone"], "DDI-2",
              severity="minor"),
        ],
    },
    "three_factors_and_cap_free": {
        "warnings": [w("interaction", ["A", "B", "C"], "DDI-3",
                       severity="contraindicated", relevant_factors=ALL)],
        "patient_factors": old,
    },
    "cascade_one_factor": {
        "warnings": [w("cascade", ["Amlodipine", "Furosemide"], "CAS-9",
                       relevant_factors=["liver_impaired"])],
        "patient_factors": {"liver_function": "impaired"},
    },
    "ties_and_alphabetical": {
        "warnings": [
            w("interaction", ["Warfarin", "Aspirin"], "R1", severity="major"),
            w("interaction", ["amlodipine", "Zinc"], "R2", severity="major"),
            w("interaction", ["Digoxin", "Ibuprofen"], "R3", severity="major"),
            w("contraindication", ["Zolpidem"], "R4", severity="major"),
        ],
    },
    "description_filtered": {
        "warnings": [
            w("interaction", ["A", "B"], "D1", severity="moderate",
              description="Stop taking warfarin if bruising."),
            w("interaction", ["C", "D"], "D2", severity="moderate",
              description=long_desc),
            w("contraindication", ["E"], "D3", severity="minor"),
            w("cascade", ["F", "G", "H"], "D4"),
        ],
    },
    "empty": {"warnings": []},
}

out = [{"name": name, "payload": payload,
        "expected": analyse_payload(payload)}
       for name, payload in cases.items()]
dest = Path(__file__).resolve().parent.parent / "src" / "mock" / "golden.json"
dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
print(f"wrote {dest} ({len(out)} cases)")
