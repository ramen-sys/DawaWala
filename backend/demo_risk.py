"""Print scores and explanations for sample warnings.

Run from the project root:   python demo.py
Edit SAMPLE_WARNINGS and PATIENT below to try your own cases.
"""
from dawawala_risk import PatientFactors, WarningInput, score_and_explain

# Change these to see how patient factors change the scores.
PATIENT = PatientFactors(
    age_range="65_plus",        # under_18 | 18_64 | 65_plus | unknown
    kidney_function="impaired", # normal | impaired | unknown
    liver_function="unknown",   # normal | impaired | unknown
)

SAMPLE_WARNINGS = [
    WarningInput(
        "interaction", ("Warfarin", "Aspirin"), "DDI-0012", "KB-1.0.0",
        severity="major",
        relevant_factors=("age_65_plus", "kidney_impaired"),
        description="Both medicines can raise the risk of bleeding."),
    WarningInput(
        "contraindication", ("Metformin",), "CI-0044", "KB-1.0.0",
        severity="contraindicated",
        relevant_factors=("kidney_impaired",),
        condition="severe kidney problems"),
    WarningInput("duplicate", ("Paracetamol",), "DUP-001", "KB-1.0.0"),
    WarningInput(
        "duplicate", ("Ibuprofen", "Naproxen"), "TD-007", "KB-1.0.0",
        duplicate_kind="therapeutic"),
    WarningInput(
        "cascade", ("Amlodipine", "Furosemide"), "CAS-003", "KB-1.0.0",
        trigger="Amlodipine", symptom_pattern="ankle swelling",
        downstream="Furosemide"),
]

for rank, sw in enumerate(score_and_explain(SAMPLE_WARNINGS, PATIENT), 1):
    w = sw.warning
    print(f"#{rank}  {w.category.value.upper()}  {' + '.join(w.medicines)}")
    print(f"    Score: {sw.score}/100   Band: {sw.band}")
    for f in sw.factors:
        print(f"      +{f.points:<3} {f.label}")
    if sw.capped:
        print(f"      (raw total {sw.raw_total}, capped at 100)")
    print(f"    Explanation: {sw.explanation}")
    print()
