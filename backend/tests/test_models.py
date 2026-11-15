import unittest

from dawawala_risk.models import (
    Category, PatientFactors, ScoredWarning, ScoreFactor, WarningInput)
from tests.common import cascade, contra, ddi, dup


class CategoryTests(unittest.TestCase):
    def test_parse(self):
        self.assertIs(Category.parse("DDI"), Category.INTERACTION)
        self.assertIs(Category.parse(" Cascade "), Category.CASCADE)
        self.assertIs(Category.parse(Category.DUPLICATE), Category.DUPLICATE)
        with self.assertRaises(ValueError):
            Category.parse("nonsense")


class PatientFactorTests(unittest.TestCase):
    def test_defaults_unknown_and_inactive(self):
        p = PatientFactors()
        self.assertEqual(p.age_range, "unknown")
        self.assertEqual(p.active_factors(), frozenset())

    def test_active_factors(self):
        p = PatientFactors("65_plus", "impaired", "impaired")
        self.assertEqual(p.active_factors(), {
            "age_65_plus", "kidney_impaired", "liver_impaired"})
        self.assertEqual(
            PatientFactors("18_64", "normal", "unknown").active_factors(),
            frozenset())

    def test_validation_and_case(self):
        self.assertEqual(PatientFactors(" 65_PLUS ").age_range, "65_plus")
        for kwargs in ({"age_range": "old"}, {"kidney_function": "bad"},
                       {"liver_function": "bad"}):
            with self.assertRaises(ValueError):
                PatientFactors(**kwargs)

    def test_from_dict(self):
        self.assertEqual(PatientFactors.from_dict(None), PatientFactors())
        p = PatientFactors.from_dict({"age_range": "under_18",
                                      "kidney_function": "impaired"})
        self.assertEqual(p.age_range, "under_18")
        self.assertEqual(p.kidney_function, "impaired")


class WarningInputTests(unittest.TestCase):
    def test_valid_warnings(self):
        self.assertEqual(ddi().severity, "major")
        self.assertEqual(ddi(severity=" MAJOR ").severity, "major")
        self.assertEqual(contra().category, Category.CONTRAINDICATION)
        self.assertEqual(dup().duplicate_kind, "exact")
        self.assertEqual(cascade().category, Category.CASCADE)

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            ddi(meds=())
        with self.assertRaises(ValueError):
            ddi(meds=("  ",))
        with self.assertRaises(ValueError):
            ddi(rule=" ")
        with self.assertRaises(ValueError):
            WarningInput("interaction", ("A", "B"), "R", " ", "major")
        with self.assertRaises(ValueError):
            ddi(factors=("bogus",))
        with self.assertRaises(ValueError):
            WarningInput("interaction", ("A", "B"), "R", "K")  # no severity
        with self.assertRaises(ValueError):
            WarningInput("contraindication", ("A",), "R", "K", "  ")
        with self.assertRaises(ValueError):
            dup(kind="weird")

    def test_from_dict_roundtrip(self):
        w = WarningInput.from_dict({
            "category": "DDI", "medicines": ["B", "A"], "rule_id": "R1",
            "kb_version": "K1", "severity": "Moderate",
            "relevant_factors": ["age_65_plus"], "description": None})
        self.assertEqual(w.category, Category.INTERACTION)
        self.assertEqual(w.description, "")
        self.assertEqual(w.relevant_factors, ("age_65_plus",))
        self.assertEqual(w.sort_name, "a + b")

    def test_scored_warning_enforces_breakdown_sum(self):
        with self.assertRaises(ValueError):
            ScoredWarning(ddi(), 10, 10, False, "Low",
                          (ScoreFactor("x", "x", 5),))

    def test_to_dict(self):
        d = ScoredWarning(ddi(), 10, 10, False, "Low",
                          (ScoreFactor("x", "X", 10),), "text").to_dict()
        self.assertEqual(d["factors"], [
            {"code": "x", "label": "X", "points": 10}])
        self.assertEqual(d["category"], "interaction")
        self.assertEqual(d["explanation"], "text")


if __name__ == "__main__":
    unittest.main()
