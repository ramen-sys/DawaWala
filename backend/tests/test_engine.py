import json
import time
import unittest

from dawawala_risk import (
    PatientFactors, WarningInput, analyse_payload, score_and_explain)
from dawawala_risk.config import load_default_config
from tests.common import cascade, contra, ddi, dup

ALL = ("age_65_plus", "kidney_impaired", "liver_impaired")


class EngineTests(unittest.TestCase):
    def test_ranked_scored_and_explained(self):
        ranked = score_and_explain([dup(), ddi("contraindicated"),
                                    cascade(), contra("minor")])
        self.assertEqual([r.score for r in ranked], [70, 30, 25, 10])
        for sw in ranked:
            # QA-EXP-01 / QA-EXP-02: explanation and breakdown always present
            self.assertTrue(sw.explanation)
            self.assertTrue(sw.factors)
            self.assertEqual(sum(f.points for f in sw.factors), sw.raw_total)

    def test_empty_list(self):
        self.assertEqual(score_and_explain([]), [])

    def test_repeated_runs_identical(self):
        # QA-REL-01
        warnings = [ddi(factors=ALL, rule=f"R{i}") for i in range(20)]
        warnings += [dup(rule="D"), cascade(rule="C")]
        patient = PatientFactors("65_plus", "impaired", "unknown")
        runs = [json.dumps([s.to_dict() for s in
                            score_and_explain(warnings, patient)])
                for _ in range(5)]
        self.assertEqual(len(set(runs)), 1)

    def test_changing_factors_changes_score(self):
        w = [ddi("moderate", factors=ALL)]
        base = score_and_explain(w)[0].score
        more = score_and_explain(w, PatientFactors("65_plus"))[0].score
        self.assertEqual((base, more), (30, 35))

    def test_performance_100_warnings_under_500ms(self):
        # PERF-06
        warnings = []
        for i in range(100):
            warnings.append(ddi("major", (f"DrugA{i}", f"DrugB{i}"),
                                f"R{i}", factors=ALL,
                                description="Raises the chance of bleeding."))
        patient = PatientFactors("65_plus", "impaired", "impaired")
        cfg = load_default_config()
        start = time.perf_counter()
        score_and_explain(warnings, patient, cfg)
        self.assertLess(time.perf_counter() - start, 0.5)


class PayloadTests(unittest.TestCase):
    def test_json_in_json_out(self):
        payload = {
            "warnings": [
                {"category": "DDI", "medicines": ["Warfarin", "Aspirin"],
                 "rule_id": "DDI-12", "kb_version": "KB-1.0.0",
                 "severity": "Major", "relevant_factors": ["age_65_plus"]},
                {"category": "duplicate", "medicines": ["Paracetamol"],
                 "rule_id": "DUP-1", "kb_version": "KB-1.0.0"},
            ],
            "patient_factors": {"age_range": "65_plus"},
        }
        out = analyse_payload(payload)
        json.dumps(out)  # must be serialisable for the API
        self.assertEqual([w["score"] for w in out["warnings"]], [55, 30])
        self.assertEqual(out["warnings"][0]["band"], "High")
        self.assertEqual(out["band_counts"], {
            "Low": 0, "Moderate": 1, "High": 1, "Critical": 0})
        self.assertEqual([f["points"] for f in out["warnings"][0]["factors"]],
                         [50, 5])

    def test_empty_payload(self):
        out = analyse_payload({})
        self.assertEqual(out["warnings"], [])
        self.assertEqual(sum(out["band_counts"].values()), 0)

    def test_bad_warning_is_rejected(self):
        with self.assertRaises(ValueError):
            analyse_payload({"warnings": [{
                "category": "interaction", "medicines": ["A"],
                "rule_id": "R", "kb_version": "K"}]})  # missing severity

    def test_from_dict_requires_core_fields(self):
        with self.assertRaises(KeyError):
            WarningInput.from_dict({"category": "interaction"})


if __name__ == "__main__":
    unittest.main()
