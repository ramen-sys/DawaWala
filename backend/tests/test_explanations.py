import unittest
from datetime import date, timedelta

from dawawala_risk import templates as T
from dawawala_risk.config import load_default_config
from dawawala_risk.explanations import (
    build_explanation, explain, forbidden_phrases, join_names, kb_notice,
    word_count)
from dawawala_risk.models import PatientFactors
from dawawala_risk.readability import flesch_kincaid_grade
from dawawala_risk.scoring import score_warning
from tests.common import cascade, contra, ddi, dup, make_config

CFG = load_default_config()
OLD = PatientFactors("65_plus", "impaired", "impaired")
ALL = ("age_65_plus", "kidney_impaired", "liver_impaired")


def explained(w, patient=None, cfg=CFG):
    return explain(score_warning(w, patient, cfg), cfg)


def every_warning_variant():
    out = []
    for sev in CFG.severity_points:
        out.append(ddi(sev, factors=ALL, description="Raises bleeding risk."))
        out.append(contra(sev, condition="severe kidney problems",
                          factors=ALL))
        out.append(contra(sev))
    out += [dup(), dup(("Ibuprofen", "Naproxen"), kind="therapeutic"),
            cascade(trigger="Amlodipine", symptom_pattern="ankle swelling",
                    downstream="Furosemide", factors=ALL),
            cascade()]
    return out


class TemplateSafetyTests(unittest.TestCase):
    """SAF-06: review of 100% of explanation templates."""

    def _all_template_strings(self):
        for name, value in vars(T).items():
            if name.startswith("_"):
                continue
            if isinstance(value, str):
                yield name, value
            elif isinstance(value, dict):
                for key, text in value.items():
                    yield f"{name}[{key}]", text

    def test_no_template_tells_user_to_start_stop_or_change(self):
        checked = 0
        for name, text in self._all_template_strings():
            self.assertEqual(forbidden_phrases(text), [], name)
            checked += 1
        self.assertGreater(checked, 15)

    def test_forbidden_detector_catches_instructions(self):
        for bad in ("Stop taking aspirin.", "You should stop it now.",
                    "Do not take this medicine.", "Don't use it.",
                    "Increase your dose.", "Switch to another drug.",
                    "This combination is safe.", "Use it safely.",
                    "Discontinue the medicine.", "You must start taking it.",
                    "Switch to another drug.", "Change the dose.",
                    "Stop the medicine.", "Lower your dosage."):
            self.assertTrue(forbidden_phrases(bad), bad)

    def test_forbidden_detector_allows_normal_text(self):
        for ok in ("Taking the same medicine twice may give too much.",
                   "Discuss this with your doctor or pharmacist.",
                   "It may change how a medicine works.",
                   "The unsafe-sounding word is not matched here.",
                   "It may lower the risk of harm.",
                   "It may reduce the effect of another medicine."):
            self.assertEqual(forbidden_phrases(ok), [], ok)

    def test_every_template_mentions_a_professional_or_is_a_fragment(self):
        self.assertIn("doctor or pharmacist", T.ADVICE)
        self.assertIn("doctor or pharmacist", T.DISCLAIMER)
        self.assertIn("not medical advice", T.DISCLAIMER)


class ExplanationContentTests(unittest.TestCase):
    def test_every_variant_meets_fr13_and_qa_exp(self):
        for w in every_warning_variant():
            sw = explained(w, OLD)
            text = sw.explanation
            label = f"{w.category.value}/{w.severity}"
            # what was found + why it matters (non-trivial text)
            self.assertGreater(word_count(text), 15, label)
            # at most 150 words
            self.assertLessEqual(word_count(text), 150, label)
            # rule ID + KB version (QA-EXP-04)
            self.assertIn(w.rule_id, text, label)
            self.assertIn(w.kb_version, text, label)
            # discuss with doctor or pharmacist
            self.assertIn("doctor or pharmacist", text, label)
            # SAF-06 / SAF-03
            self.assertEqual(forbidden_phrases(text), [], label)
            # grade 9 or lower for each one
            self.assertLessEqual(flesch_kincaid_grade(text), 9.0, label)

    def test_average_grade_is_at_most_9(self):
        grades = [flesch_kincaid_grade(explained(w, OLD).explanation)
                  for w in every_warning_variant()]
        self.assertLessEqual(sum(grades) / len(grades), 9.0)

    def test_interaction_text(self):
        t = explained(ddi("major", ("Warfarin", "Aspirin"))).explanation
        self.assertIn("possible interaction between Warfarin and Aspirin", t)
        self.assertIn("major", t)

    def test_contraindication_with_and_without_condition(self):
        with_c = explained(contra(condition="severe kidney problems"))
        self.assertIn("people with severe kidney problems",
                      with_c.explanation)
        without = explained(contra())
        self.assertIn("may not be suitable for you", without.explanation)

    def test_duplicate_texts(self):
        exact = explained(dup(("Paracetamol",))).explanation
        self.assertIn("Paracetamol more than once", exact)
        thera = explained(dup(("Ibuprofen", "Naproxen"),
                              kind="therapeutic")).explanation
        self.assertIn("Ibuprofen and Naproxen", thera)
        self.assertIn("possible duplication", thera)

    def test_cascade_is_worded_as_possible_never_diagnosis(self):
        t = explained(cascade(trigger="Amlodipine",
                              symptom_pattern="ankle swelling",
                              downstream="Furosemide")).explanation
        self.assertIn("possible prescribing cascade", t)
        self.assertIn("Amlodipine may cause ankle swelling", t)
        self.assertIn("not a diagnosis", t)

    def test_cascade_without_detail_falls_back_to_medicines(self):
        t = explained(cascade(meds=("A", "B", "C"))).explanation
        self.assertIn("The medicines involved are A, B and C.", t)

    def test_unconfigured_severity_wording_falls_back(self):
        cfg = make_config(severity_points={"critical-ish": 40})
        t = explained(ddi("critical-ish"), cfg=cfg).explanation
        self.assertIn("rates it as critical-ish", t)
        t = explained(contra("critical-ish"), cfg=cfg).explanation
        self.assertIn("rated as critical-ish", t)

    def test_patient_factor_line_only_when_factors_applied(self):
        with_p = explained(ddi(factors=("kidney_impaired",
                                        "age_65_plus")), OLD).explanation
        self.assertIn("age 65 or over and impaired kidney function",
                      with_p)
        self.assertNotIn("raised its priority score",
                         explained(ddi(factors=ALL)).explanation)

    def test_explanation_is_deterministic(self):
        w = ddi(factors=ALL, description="Raises bleeding risk.")
        self.assertEqual(explained(w, OLD).explanation,
                         explained(w, OLD).explanation)


class KnowledgeBaseDescriptionTests(unittest.TestCase):
    def test_safe_description_included(self):
        sw = explained(ddi(description="Both raise bleeding risk."))
        self.assertIn("Both raise bleeding risk.", sw.explanation)
        self.assertEqual(sw.explanation_notes, ())

    def test_description_with_instruction_is_dropped(self):
        sw = explained(ddi(description="Stop taking warfarin if bruising."))
        self.assertNotIn("Stop taking", sw.explanation)
        self.assertEqual(forbidden_phrases(sw.explanation), [])
        self.assertTrue(any("forbidden" in n for n in sw.explanation_notes))

    def test_long_description_is_cut_at_a_sentence_boundary(self):
        desc = " ".join(f"Sentence number {i} is here." for i in range(60))
        sw = explained(ddi(description=desc))
        self.assertLessEqual(word_count(sw.explanation), 150)
        self.assertTrue(any("shortened" in n for n in sw.explanation_notes))
        self.assertIn("Sentence number 0 is here.", sw.explanation)

    def test_description_that_cannot_fit_is_omitted(self):
        huge = "word " * 400 + "end."
        sw = explained(ddi(description=huge))
        self.assertLessEqual(word_count(sw.explanation), 150)
        self.assertTrue(any("word limit" in n for n in sw.explanation_notes))

    def test_blank_description_ignored(self):
        self.assertEqual(
            explained(ddi(description="   ")).explanation_notes, ())


class FailClosedTests(unittest.TestCase):
    def test_medicine_names_cannot_smuggle_instructions(self):
        sw = score_warning(ddi(meds=("Stop taking aspirin", "Warfarin")),
                           None, CFG)
        with self.assertRaises(ValueError):
            build_explanation(sw, CFG)

    def test_too_long_explanation_raises_rather_than_truncating(self):
        cfg = make_config(explanation_max_words=20)
        sw = score_warning(ddi(), None, cfg)
        with self.assertRaises(ValueError):
            build_explanation(sw, cfg)


class HelperTests(unittest.TestCase):
    def test_join_names(self):
        self.assertEqual(join_names([]), "")
        self.assertEqual(join_names(["A"]), "A")
        self.assertEqual(join_names(["A", "B"]), "A and B")
        self.assertEqual(join_names(["A", "B", "C"]), "A, B and C")

    def test_kb_notice(self):
        today = date(2026, 10, 22)
        fresh = today - timedelta(days=180)
        stale = today - timedelta(days=181)
        self.assertIsNone(kb_notice(fresh, today, CFG))
        notice = kb_notice(stale, today, CFG)
        self.assertIn("180 days", notice)
        self.assertIn("out of date", notice)

    def test_kb_notice_defaults_to_today(self):
        self.assertIsNotNone(kb_notice(date(2000, 1, 1), None, CFG))
        self.assertIsNone(kb_notice(date.today(), None, CFG))


if __name__ == "__main__":
    unittest.main()
