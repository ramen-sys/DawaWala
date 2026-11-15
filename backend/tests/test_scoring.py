import unittest

from dawawala_risk.config import load_default_config
from dawawala_risk.models import PatientFactors
from dawawala_risk.scoring import (
    band_counts, band_for, rank_warnings, score_warning, sort_key)
from tests.common import cascade, contra, ddi, dup, make_config

ALL = ("age_65_plus", "kidney_impaired", "liver_impaired")
OLD_KIDNEY_LIVER = PatientFactors("65_plus", "impaired", "impaired")


class SeverityScoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_default_config()

    def test_interaction_severity_points(self):
        for sev, pts in (("minor", 10), ("moderate", 30), ("major", 50),
                         ("contraindicated", 70)):
            sw = score_warning(ddi(severity=sev), None, self.cfg)
            self.assertEqual(sw.score, pts)
            self.assertEqual(len(sw.factors), 1)
            self.assertIn("interaction", sw.factors[0].label)

    def test_contraindication_uses_same_scale(self):
        sw = score_warning(contra(severity="major"), None, self.cfg)
        self.assertEqual(sw.score, 50)
        self.assertIn("contraindication", sw.factors[0].label)

    def test_duplicate_and_therapeutic(self):
        self.assertEqual(score_warning(dup(), None, self.cfg).score, 30)
        sw = score_warning(dup(kind="therapeutic"), None, self.cfg)
        self.assertEqual(sw.score, 15)
        self.assertEqual(sw.factors[0].code, "therapeutic_duplication")

    def test_cascade(self):
        self.assertEqual(score_warning(cascade(), None, self.cfg).score, 25)

    def test_unknown_severity_is_an_error_not_zero(self):
        with self.assertRaises(ValueError):
            score_warning(ddi(severity="catastrophic"), None, self.cfg)

    def test_default_config_and_patient_loaded_when_omitted(self):
        self.assertEqual(score_warning(ddi(severity="minor")).score, 10)


class SrsWorkedExampleTests(unittest.TestCase):
    """The two examples printed under Table 5.2 of the SRS."""

    def setUp(self):
        self.cfg = load_default_config()

    def test_contraindicated_with_two_factors_is_80_critical(self):
        w = ddi(severity="contraindicated",
                factors=("age_65_plus", "kidney_impaired"))
        sw = score_warning(w, OLD_KIDNEY_LIVER, self.cfg)
        self.assertEqual(sw.score, 80)
        self.assertEqual(sw.band, "Critical")
        self.assertEqual([f.points for f in sw.factors], [70, 5, 5])

    def test_cascade_with_one_factor_is_30_moderate(self):
        w = cascade(factors=("liver_impaired",))
        sw = score_warning(w, PatientFactors(liver_function="impaired"),
                           self.cfg)
        self.assertEqual(sw.score, 30)
        self.assertEqual(sw.band, "Moderate")


class PatientFactorTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_default_config()

    def test_only_factors_the_rule_lists_count(self):
        sw = score_warning(ddi(severity="minor", factors=("kidney_impaired",)),
                           OLD_KIDNEY_LIVER, self.cfg)
        self.assertEqual(sw.score, 15)

    def test_unknown_or_normal_factors_never_count(self):
        w = ddi(severity="minor", factors=ALL)
        for p in (PatientFactors(),
                  PatientFactors("18_64", "normal", "normal"),
                  PatientFactors("under_18")):
            self.assertEqual(score_warning(w, p, self.cfg).score, 10)

    def test_factor_never_counted_twice_and_max_15(self):
        w = ddi(severity="minor", factors=ALL + ALL[:1])
        sw = score_warning(w, OLD_KIDNEY_LIVER, self.cfg)
        self.assertEqual(sw.score, 25)
        self.assertEqual(len(sw.factors), 4)

    def test_patient_factor_max_is_configurable_and_clips_points(self):
        cfg = make_config(patient_factor_max=7)
        sw = score_warning(ddi(severity="minor", factors=ALL),
                           OLD_KIDNEY_LIVER, cfg)
        self.assertEqual([f.points for f in sw.factors], [10, 5, 2])
        self.assertEqual(sw.score, 17)

    def test_patient_factor_max_zero_adds_nothing(self):
        cfg = make_config(patient_factor_max=0)
        sw = score_warning(ddi(severity="minor", factors=ALL),
                           OLD_KIDNEY_LIVER, cfg)
        self.assertEqual(sw.score, 10)


class CapAndBreakdownTests(unittest.TestCase):
    def test_cap_at_100_but_breakdown_shows_raw_total(self):
        cfg = make_config(severity_points={"contraindicated": 95})
        w = ddi(severity="contraindicated", factors=ALL)
        sw = score_warning(w, OLD_KIDNEY_LIVER, cfg)
        self.assertEqual(sw.raw_total, 110)
        self.assertEqual(sw.score, 100)
        self.assertTrue(sw.capped)
        self.assertEqual(sum(f.points for f in sw.factors), sw.raw_total)

    def test_not_capped_when_under_limit(self):
        sw = score_warning(ddi(), None, load_default_config())
        self.assertFalse(sw.capped)

    def test_breakdown_always_sums_to_raw_total(self):
        cfg = load_default_config()
        for w in (ddi(), contra(), dup(), dup(kind="therapeutic"), cascade(),
                  ddi(severity="contraindicated", factors=ALL)):
            sw = score_warning(w, OLD_KIDNEY_LIVER, cfg)
            self.assertEqual(sum(f.points for f in sw.factors), sw.raw_total)
            self.assertEqual(sw.score, min(sw.raw_total, 100))


class BandTests(unittest.TestCase):
    def test_boundaries(self):
        cfg = load_default_config()
        cases = {0: "Low", 24: "Low", 25: "Moderate", 49: "Moderate",
                 50: "High", 74: "High", 75: "Critical", 100: "Critical"}
        for score, band in cases.items():
            self.assertEqual(band_for(score, cfg), band, score)

    def test_band_counts(self):
        cfg = load_default_config()
        scored = [score_warning(w, None, cfg) for w in (
            ddi("minor"), ddi("major"), ddi("major", rule="R2"), dup())]
        self.assertEqual(band_counts(scored), {
            "Low": 1, "Moderate": 1, "High": 2, "Critical": 0})


class SortingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_default_config()

    def _rank(self, warnings, patient=None):
        scored = [score_warning(w, patient, self.cfg) for w in warnings]
        return rank_warnings(scored, self.cfg)

    def test_highest_score_first(self):
        ranked = self._rank([dup(), ddi("contraindicated"), cascade()])
        self.assertEqual([r.score for r in ranked], [70, 30, 25])

    def test_ties_broken_by_category_order(self):
        # Default cascade is 25, so use a config where all four score 30.
        cfg = make_config(cascade_points=30)
        warnings = [dup(rule="d"), cascade(rule="c"),
                    ddi("moderate", rule="i"), contra("moderate", rule="k")]
        scored = [score_warning(w, None, cfg) for w in warnings]
        ranked = rank_warnings(scored, cfg)
        self.assertEqual([r.warning.category.value for r in ranked],
                         ["contraindication", "interaction", "cascade",
                          "duplicate"])

    def test_ties_then_alphabetical_case_insensitive(self):
        ranked = self._rank([
            ddi("major", ("Warfarin", "Aspirin"), "R1"),
            ddi("major", ("amlodipine", "Zinc"), "R2"),
            ddi("major", ("Digoxin", "Ibuprofen"), "R3")])
        self.assertEqual([r.warning.rule_id for r in ranked],
                         ["R2", "R1", "R3"])

    def test_rule_id_is_final_tiebreak(self):
        ranked = self._rank([ddi(rule="B"), ddi(rule="A")])
        self.assertEqual([r.warning.rule_id for r in ranked], ["A", "B"])

    def test_deterministic_for_any_input_order(self):
        warnings = [ddi("major", ("A", "B"), "R1"), dup(rule="R2"),
                    cascade(rule="R3"), contra("minor", rule="R4"),
                    ddi("major", ("C", "D"), "R5")]
        expected = [r.warning.rule_id for r in self._rank(warnings)]
        for shift in range(len(warnings)):
            rotated = warnings[shift:] + warnings[:shift]
            self.assertEqual(
                [r.warning.rule_id for r in self._rank(rotated)], expected)
            self.assertEqual(
                [r.warning.rule_id for r in self._rank(rotated[::-1])],
                expected)

    def test_sort_key_shape(self):
        sw = score_warning(ddi(), None, self.cfg)
        self.assertEqual(sort_key(sw, self.cfg)[0], -50)


if __name__ == "__main__":
    unittest.main()
