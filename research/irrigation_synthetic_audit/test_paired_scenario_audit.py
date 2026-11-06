"""Negative-path checks for the strict synthetic scenario postprocessor."""

import csv
import math
import tempfile
import unittest
from pathlib import Path

from research.irrigation_synthetic_audit.paired_scenario_audit import (AuditError, FIELDS, analyze_family, load_records)


def rows_for_family(family):
    policies = ("integrated", "v2", "v3") if family == "C" else (
        "integrated", "integrated_forecast_ET", "v2", "v3")
    for path_id in range(12):
        climate = ("dry", "medium", "wet")[path_id // 4]
        for bias in (-.02, -.01, 0, .01, .02):
            for et in (.85, 1., 1.15):
                for weather_case in ("perfect", "missing", "falsePositive"):
                    for policy in policies:
                        yield {
                            "cohort": f"{family}-{climate}-{path_id}",
                            "seed": 1000 + path_id, "climate_class": climate,
                            "bias_vwc": bias, "et_forecast_multiplier": et,
                            "forecast_case": weather_case, "policy": policy,
                            "gross_water_m3": 110 if policy == "v3" else 100,
                            "irrigation_events": 6, "q_positive_plot_days":
                            8 if policy == "v3" else 10,
                            "below_98_plot_days": 7 if policy == "v3" else 9,
                            "drainage_sum_mm": 0,
                        }


class AuditTests(unittest.TestCase):
    def make_records(self, family, edits=None):
        raw = list(rows_for_family(family))
        if edits:
            edits(raw)
        with tempfile.TemporaryDirectory() as dirname:
            file = Path(dirname) / "source.csv"
            with file.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(raw)
            return load_records(file)

    def test_full_factorial_and_lambda_switch(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertEqual((result["record_count"], result["matched_keys"]), (1620, 540))
        self.assertEqual(result["comparisons"]["q_better_water_worse"], 540)
        self.assertEqual(result["weights"]["0"]["v2"], 540)
        self.assertEqual(result["weights"]["10"]["v3"], 540)

    def test_four_policy_regime(self):
        result = analyze_family(self.make_records("R1"), "R1")
        self.assertEqual((result["record_count"], result["matched_keys"]), (2160, 540))

    def test_duplicate_key_rejected(self):
        def duplicate(rows):
            rows[1] = rows[0].copy()
        with self.assertRaisesRegex(AuditError, "duplicate"):
            analyze_family(self.make_records("C", duplicate), "C")

    def test_nonfinite_numeric_rejected(self):
        def nan_water(rows):
            rows[0]["gross_water_m3"] = math.nan
        with self.assertRaisesRegex(AuditError, "Nonfinite"):
            self.make_records("C", nan_water)

    def test_water_cap_rejected(self):
        def over_cap(rows):
            rows[0]["gross_water_m3"] = 321
        with self.assertRaisesRegex(AuditError, "cap"):
            self.make_records("C", over_cap)

    def test_incomplete_policy_rejected(self):
        def missing(rows):
            rows.pop()
        with self.assertRaisesRegex(AuditError, "rows"):
            analyze_family(self.make_records("R1", missing), "R1")

    def test_unsupported_bias_rejected(self):
        def unsupported(rows):
            rows[0]["bias_vwc"] = .3
        with self.assertRaisesRegex(AuditError, "sensor bias"):
            self.make_records("C", unsupported)


if __name__ == "__main__":
    unittest.main()
