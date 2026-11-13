"""FR-13: plain-language explanation for every warning.

Each explanation states what was found, why it matters (the knowledge-base description),
which rule and knowledge-base version produced it, and that the user should discuss it with a
doctor or pharmacist. It never tells the user to start, stop or change a medicine (SAF-06) and
is at most EXPLANATION_MAX_WORDS words. Cascades are always worded as possible, never as a
diagnosis (FR-12).
"""

from __future__ import annotations

from app.core.config import settings
from app.engine import SafetyWarning
from app.engine.models import CASCADE, CONTRAINDICATION, DDI

CONSULT = "Please discuss this with your doctor or pharmacist."

FACTOR_PHRASES = {
    "age_range:under_18": "being under 18",
    "age_range:18_64": "being aged 18 to 64",
    "age_range:65_plus": "being 65 or over",
    "kidney_function:impaired": "reduced kidney function",
    "kidney_function:normal": "normal kidney function",
    "liver_function:impaired": "reduced liver function",
    "liver_function:normal": "normal liver function",
}


def _join(names) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _phrase(token: str) -> str:
    return FACTOR_PHRASES.get(token, token.replace("_", " ").replace(":", ": "))


def _finding(w: SafetyWarning) -> str:
    names = _join(w.medication_names)
    d = w.details
    if w.category == DDI:
        text = f"A possible interaction was found between {names}."
        via = d.get("via")
        if via:
            text += f" The rule is about {_join(via)}, which these medicines contain."
        return text
    if w.category == CONTRAINDICATION:
        condition = _phrase(d.get("condition", ""))
        text = f"{names} may not be suitable for a patient with {condition}."
        if d.get("via"):
            text += f" It contains {d['via']}."
        return text
    if w.category == CASCADE:
        return (f"These medicines may form a prescribing cascade: {_join(d.get('trigger_names', []))} can "
                f"sometimes cause {d.get('symptom_pattern', 'a side effect')}, which is sometimes treated "
                f"with {_join(d.get('downstream_names', []))}. This is only a possibility.")
    # duplicate
    if d.get("kind") == "therapeutic":
        return f"{names} belong to the same group of medicines ({d.get('drug_class', '')}), so they may do the same job twice."
    if d.get("ingredient"):
        return f"{names} all contain {d['ingredient']}."
    entered = d.get("entered_as") or []
    return f"{names} is listed more than once" + (f" (as {_join(entered)})." if entered else ".")


def _factors_sentence(w: SafetyWarning) -> str:
    if not w.matched_factors:
        return ""
    return f"This may matter more because of {_join(_phrase(t) for t in w.matched_factors)}."


def _truncate(text: str, max_words: int) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[: max_words - 1]) + " …"


def explain(warning: SafetyWarning) -> str:
    finding = _finding(warning)
    why = warning.description.strip()
    factors = _factors_sentence(warning)
    rule = f"Rule {warning.rule_id}, knowledge base version {warning.kb_version}."
    budget = settings.EXPLANATION_MAX_WORDS - len(f"{rule} {CONSULT}".split())
    # The rule reference and the advice to consult are always kept; only the body can be shortened.
    body = _truncate(" ".join(part for part in (finding, why, factors) if part), budget)
    return f"{body} {rule} {CONSULT}"
