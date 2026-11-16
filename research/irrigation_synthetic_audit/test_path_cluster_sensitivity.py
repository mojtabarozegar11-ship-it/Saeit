"""Executable R01 synthetic-climate-path diagnostics (NOT field validation)."""
import contextlib
import copy
import io
import json
import math
import statistics
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.irrigation_synthetic_audit.path_cluster_sensitivity import (
    SensitivityError, load_report, main, summarize_family,
)

CLASSES = ("dry", "medium", "wet")
FIELDS = ("mean_delta_water_m3", "mean_delta_q100")


def fixture(family="C", water=None, q=None):
    # Deliberately fictional 12-path test data, NOT author R01 measurements.
    water = list(range(1, 13)) if water is None else water
    q = [-1 - 2 * i for i in range(12)] if q is None else q
    prefix = "C" if family == "C" else "R"
    path = []
    for i in range(12):
        climate = CLASSES[i // 4]
        path.append({
            "cohort": f"{prefix}-{climate}-{i % 4 + 1}",
            "seed": i + 1, "climate_class": climate,
            "matched_keys": 45,
            "mean_delta_water_m3": water[i], "mean_delta_q100": q[i],
        })
    leave = []
    for i, row in enumerate(path):
        leave.append({
            "excluded_path": row["cohort"], "excluded_seed": row["seed"],
            "climate_class": row["climate_class"],
            "remaining_matched_keys": 495,
            "mean_delta_water_m3": statistics.fmean(water[:i] + water[i+1:]),
            "mean_delta_q100": statistics.fmean(q[:i] + q[i+1:]),
        })
    cl = {}
    for i, climate in enumerate(CLASSES):
        a, b = i * 4, (i + 1) * 4
        cl[climate] = {
            "matched_keys": 180, "climate_paths": 4,
            "mean_delta_water_m3": statistics.fmean(water[a:b]),
            "mean_delta_q100": statistics.fmean(q[a:b]),
        }
    return {
        "family": family, "record_count": 1620 if family == "C" else 2160,
        "matched_keys": 540, "climate_paths": 12,
        "climate_path_effects": path,
        "climate_class_effects": cl, "leave_one_climate_path_out": leave,
        "mean_delta_water_m3": statistics.fmean(water),
        "mean_delta_q100": statistics.fmean(q),
    }


class TestR01ClusterSensitivity(unittest.TestCase):
    def test_c_family_descriptive_mean(self):
        self.assertEqual(summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]["finite_archive_mean"], 6.5)

    def test_r1_family_accepted_without_r1_prefix(self):
        self.assertEqual(summarize_family(fixture("R1"))["family"], "R1")

    def test_twelve_independent_path_blocks_not_540_farms(self):
        self.assertEqual(summarize_family(fixture())["independent_climate_path_blocks"], 12)

    def test_each_path_has_45_factorial_settings(self):
        self.assertEqual(summarize_family(fixture())["factorial_settings_per_path"], 45)

    def test_q100_direction_preserved(self):
        self.assertLess(summarize_family(fixture())["outcomes"]["mean_delta_q100"]["finite_archive_mean"], 0)

    def test_sample_sd_uses_12_paths(self):
        output = summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]
        self.assertAlmostEqual(output["path_sd_descriptive"], statistics.stdev(range(1, 13)))

    def test_standard_error_not_claimed_as_interval(self):
        obj = summarize_family(fixture())
        self.assertFalse(obj["interval_coverage_claim"])
        output = obj["outcomes"]["mean_delta_water_m3"]
        self.assertAlmostEqual(output["path_se_descriptive_only"],
                               statistics.stdev(range(1, 13)) / math.sqrt(12))

    def test_leave_one_out_denominator_is_11_paths(self):
        out = summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]["leave_one_path_out"]
        self.assertEqual({r["remaining_paths"] for r in out}, {11})

    def test_leave_one_out_exclusion_is_exact(self):
        row = summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]["leave_one_path_out"][0]
        self.assertAlmostEqual(row["leave_one_path_mean"], 77 / 11)

    def test_influence_equals_full_minus_deleted_mean(self):
        row = summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]["leave_one_path_out"][0]
        self.assertAlmostEqual(row["influence_overall_minus_leave_one_out"], 6.5 - 7)

    def test_max_absolute_influence_is_recomputed(self):
        out = summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]
        self.assertAlmostEqual(out["max_abs_leave_one_path_influence"], .5)

    def test_class_means_keep_dry_medium_wet_distinct(self):
        obj = summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]
        self.assertEqual(obj["class_means"], {"dry": 2.5, "medium": 6.5, "wet": 10.5})

    def test_sign_reversal_detected_when_outlier_removed(self):
        obj = summarize_family(fixture(water=[-50] + [1] * 11))
        self.assertTrue(obj["outcomes"]["mean_delta_water_m3"]["sign_reversal_on_deletion"])

    def test_sign_reversal_absent_for_strictly_positive_effects(self):
        self.assertFalse(summarize_family(fixture())["outcomes"]["mean_delta_water_m3"]["sign_reversal_on_deletion"])

    def test_field_validity_not_claimed(self):
        self.assertFalse(summarize_family(fixture())["field_validity_claim"])

    def test_wrong_family_path_prefix_rejected(self):
        data = fixture()
        data["climate_path_effects"][0]["cohort"] = "R-dry-1"
        with self.assertRaises(SensitivityError): summarize_family(data)

    def test_duplicate_path_identifier_rejected(self):
        data = fixture()
        data["climate_path_effects"][1]["seed"] = 1
        data["climate_path_effects"][1]["cohort"] = "C-dry-1"
        with self.assertRaisesRegex(SensitivityError, "duplicate"): summarize_family(data)

    def test_path_nonfinite_rejected(self):
        data = fixture()
        data["climate_path_effects"][0]["mean_delta_q100"] = float("nan")
        with self.assertRaisesRegex(SensitivityError, "finite"): summarize_family(data)

    def test_boolean_disguised_as_numeric_rejected(self):
        data = fixture()
        data["climate_path_effects"][0]["mean_delta_water_m3"] = True
        with self.assertRaisesRegex(SensitivityError, "finite"): summarize_family(data)

    def test_wrong_policy_row_count_rejected(self):
        data = fixture()
        data["record_count"] = 2160
        with self.assertRaises(SensitivityError): summarize_family(data)

    def test_missing_one_path_rejected(self):
        data = fixture()
        data["climate_path_effects"].pop()
        with self.assertRaises(SensitivityError): summarize_family(data)

    def test_unbalanced_climate_paths_rejected(self):
        data = fixture()
        data["climate_path_effects"][4]["climate_class"] = "dry"
        data["climate_path_effects"][4]["cohort"] = "C-dry-5"
        with self.assertRaises(SensitivityError): summarize_family(data)

    def test_wrong_class_arithmetic_rejected(self):
        data = fixture()
        data["climate_class_effects"]["wet"]["mean_delta_water_m3"] = 9
        with self.assertRaisesRegex(SensitivityError, "class mean"): summarize_family(data)

    def test_wrong_global_arithmetic_rejected(self):
        data = fixture()
        data["mean_delta_q100"] += 1
        with self.assertRaisesRegex(SensitivityError, "global mean"): summarize_family(data)

    def test_wrong_loo_arithmetic_rejected(self):
        data = fixture()
        data["leave_one_climate_path_out"][0]["mean_delta_water_m3"] = 123
        with self.assertRaisesRegex(SensitivityError, "LOO disagreement"): summarize_family(data)

    def test_duplicate_loo_path_rejected(self):
        data = fixture()
        data["leave_one_climate_path_out"][1] = copy.deepcopy(data["leave_one_climate_path_out"][0])
        with self.assertRaisesRegex(SensitivityError, "duplicate"): summarize_family(data)

    def test_loo_495_settings_required(self):
        data = fixture()
        data["leave_one_climate_path_out"][0]["remaining_matched_keys"] = 494
        with self.assertRaises(SensitivityError): summarize_family(data)

    def test_malformed_negative_seed_rejected(self):
        data = fixture()
        data["climate_path_effects"][0]["seed"] = -1
        with self.assertRaisesRegex(SensitivityError, "seed"): summarize_family(data)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "input.json"
            file.write_text('{"families":[], "families":[]}')
            with self.assertRaisesRegex(SensitivityError, "duplicate JSON"):
                load_report(file)

    def test_nonfinite_json_constants_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "input.json"
            file.write_text('{"families":[NaN]}')
            with self.assertRaisesRegex(SensitivityError, "nonfinite JSON"):
                load_report(file)

    def test_cli_rejects_duplicate_families(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "input.json"
            file.write_text(json.dumps({"families": [fixture(), fixture()]}))
            with patch.object(sys, "argv", ["sensitivity", "--audit-json", str(file)]):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(), 1)

    def test_cli_valid_two_families_has_no_empirical_or_replay_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "input.json"
            file.write_text(json.dumps({"families": [fixture(), fixture("R1")]}))
            buffer = io.StringIO()
            with patch.object(sys, "argv", ["sensitivity", "--audit-json", str(file)]):
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(main(), 0)
            result = json.loads(buffer.getvalue())
            self.assertFalse(result["source_verified_independently"])
            self.assertFalse(result["generator_replayed"])
            self.assertFalse(result["decision_time_validated"])


if __name__ == "__main__":
    unittest.main()
