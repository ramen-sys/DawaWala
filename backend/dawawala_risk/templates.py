"""All user-facing explanation text lives here so it can be reviewed in one
place (SAF-06, QA-EXP-03). Rules for every string in this file:

* plain English, short sentences (Flesch-Kincaid grade 9 or lower),
* never tell the user to start, stop or change a medicine or dose,
* say "possible", never "safe" (SAF-03),
* always point the user to a doctor or pharmacist.
"""

DISCLAIMER = (
    "Decision support only. This is not medical advice. "
    "Discuss these results with your doctor or pharmacist.")

ADVICE = "Please discuss this with your doctor or pharmacist."
TRACE = "Source: rule {rule_id}, knowledge base version {kb_version}."
FACTOR_LINE = "Your answer about {factors} raised its priority score."

# --- interaction -----------------------------------------------------------
INTERACTION_FOUND = "We found a possible interaction between {medicines}."
INTERACTION_SEVERITY = {
    "minor": (
        "The knowledge base rates it as minor. The effect is usually small."),
    "moderate": (
        "The knowledge base rates it as moderate. It may change how well a "
        "medicine works, or add side effects."),
    "major": (
        "The knowledge base rates it as major. It may cause serious side "
        "effects or keep a medicine from working well."),
    "contraindicated": (
        "The knowledge base rates it as contraindicated. These medicines are "
        "not usually meant to be used together."),
}
INTERACTION_SEVERITY_DEFAULT = (
    "The knowledge base rates it as {severity}. It may affect how the "
    "medicines work.")

# --- contraindication ------------------------------------------------------
CONTRA_FOUND = "We found a possible concern about {medicines}."
CONTRA_WITH_CONDITION = (
    "The knowledge base says it may not be suitable for people with "
    "{condition}.")
CONTRA_NO_CONDITION = "The knowledge base says it may not be suitable for you."
CONTRA_SEVERITY = {
    "minor": "The concern is rated as minor. It may add mild side effects.",
    "moderate": (
        "The concern is rated as moderate. It may add side effects or make "
        "the medicine work less well."),
    "major": (
        "The concern is rated as major. It may raise the risk of harm."),
    "contraindicated": (
        "The concern is rated as contraindicated. This means the medicine is "
        "not usually meant to be used in this case."),
}
CONTRA_SEVERITY_DEFAULT = "The concern is rated as {severity}."

# --- duplicate -------------------------------------------------------------
DUPLICATE_EXACT = (
    "We found {medicines} more than once in your list, possibly under "
    "different brand names. Taking the same medicine twice may give you too "
    "much of it. That can raise the chance of side effects.")
DUPLICATE_THERAPEUTIC = (
    "We found two medicines, {medicines}, that belong to the same drug "
    "class. Medicines in one class often do a similar job. Using both may "
    "give more of the same effect than intended. This is only a possible "
    "duplication.")

# --- cascade ---------------------------------------------------------------
CASCADE_FOUND = "We found a possible prescribing cascade."
CASCADE_DETAIL = (
    "{trigger} may cause {symptom}. {downstream} is sometimes used to treat "
    "that problem.")
CASCADE_FALLBACK = "The medicines involved are {medicines}."
CASCADE_WHY = (
    "A side effect can be mistaken for a new health problem. This may not "
    "apply to you. It is not a diagnosis.")
