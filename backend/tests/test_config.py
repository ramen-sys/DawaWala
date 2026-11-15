import json
import os
import tempfile
import unittest

from dawawala_risk.config import (
    ENV_VAR, ConfigError, ScoringConfig, load_default_config)
from tests.common import default_data


class ConfigTests(unittest.TestCase):
    def test_defaults_match_srs_section_5_5(self):
        c = load_default_config()
        self.assertEqual(c.severity_points, {
            "minor": 10, "moderate": 30, "major": 50, "contraindicated": 70})
        self.assertEqual(c.duplicate_points, 30)
        self.assertEqual(c.therapeutic_duplication_points, 15)
        self.assertEqual(c.cascade_points, 25)
        self.assertEqual(c.patient_factor_points, 5)
        self.assertEqual(c.patient_factor_max, 15)
        self.assertEqual(c.score_max, 100)
        self.assertEqual(c.band_thresholds, (25, 50, 75))
        self.assertEqual(c.explanation_max_words, 150)
        self.assertEqual(c.kb_stale_days, 180)

    def _bad(self, **overrides):
        data = default_data()
        data.update(overrides)
        with self.assertRaises(ConfigError):
            ScoringConfig.from_dict(data)

    def test_invalid_values_rejected(self):
        self._bad(score_max=0)
        self._bad(score_max=-1)
        self._bad(score_max=True)
        self._bad(score_max="100")
        self._bad(duplicate_points=-5)
        self._bad(severity_points={})
        self._bad(severity_points="x")
        self._bad(severity_points={"minor": -1})
        self._bad(severity_points={"minor": 1.5})
        self._bad(band_thresholds=[25, 50])
        self._bad(band_thresholds=[25, 50, "75"])
        self._bad(band_thresholds=[50, 25, 75])
        self._bad(band_thresholds=[0, 50, 75])
        self._bad(band_thresholds=[25, 50, 101])
        self._bad(category_order=["interaction"])
        self._bad(category_order="interaction")
        self._bad(explanation_max_words=0)

    def test_missing_key_rejected(self):
        data = default_data()
        del data["cascade_points"]
        with self.assertRaises(ConfigError):
            ScoringConfig.from_dict(data)

    def test_severity_names_are_normalised(self):
        data = default_data()
        data["severity_points"] = {" Minor ": 1}
        self.assertEqual(
            ScoringConfig.from_dict(data).severity_points, {"minor": 1})

    def test_from_file_errors(self):
        with self.assertRaises(ConfigError):
            ScoringConfig.from_file("/nonexistent/config.json")
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.json")
            with open(bad, "w") as f:
                f.write("{not json")
            with self.assertRaises(ConfigError):
                ScoringConfig.from_file(bad)
            arr = os.path.join(d, "arr.json")
            with open(arr, "w") as f:
                f.write("[]")
            with self.assertRaises(ConfigError):
                ScoringConfig.from_file(arr)

    def test_environment_variable_overrides_default(self):
        data = default_data()
        data["cascade_points"] = 99
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.json")
            with open(path, "w") as f:
                json.dump(data, f)
            old = os.environ.get(ENV_VAR)
            os.environ[ENV_VAR] = path
            try:
                self.assertEqual(load_default_config().cascade_points, 99)
            finally:
                if old is None:
                    del os.environ[ENV_VAR]
                else:
                    os.environ[ENV_VAR] = old
        self.assertEqual(load_default_config().cascade_points, 25)


if __name__ == "__main__":
    unittest.main()
