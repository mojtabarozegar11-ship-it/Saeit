"""Negative-path checks for the strict synthetic scenario postprocessor."""

import copy
import csv
import hashlib
import subprocess
import sys
import math
import tempfile
import unittest
from pathlib import Path

from research.irrigation_synthetic_audit.paired_scenario_audit import (
    AuditError, EXPECTED, EXPECTED_WEIGHT_GRID, FIELDS, SOURCE_PATHS,
    analyze_family, file_sha256, load_records, verify_paper, verify_source_paths,
    verify_frozen_sha256,
)


def rows_for_family(family):
    policies = ("integrated", "v2", "v3") if family == "C" else (
        "integrated", "integrated_forecast_ET", "v2", "v3")
    prefix = "C" if family == "C" else "R"  # Matches real workbook IDs.
    for path_id in range(12):
        climate = ("dry", "medium", "wet")[path_id // 4]
        for bias in (-.02, -.01, 0, .01, .02):
            for et in (.85, 1., 1.15):
                for weather_case in ("perfect", "missing", "falsePositive"):
                    for policy in policies:
                        yield {
                            "cohort": f"{prefix}-{climate}-{path_id}",
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

    def test_drainage_depth_unit_preserved(self):
        def set_depth(rows):
            for row in rows:
                row["drainage_sum_mm"] = 12.5
        result = analyze_family(self.make_records("C", set_depth), "C")
        for policy in ("integrated", "v2", "v3"):
            self.assertEqual(result["means"][policy]["drainage_sum_mm"], 12.5)
            self.assertNotIn("drainage_m3_equivalent", result["means"][policy])

    def test_duplicate_csv_header_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "duplicate_header.csv"
            path.write_text("cohort,cohort,policy\nC-dry-0,C-dry-0,v2\n", encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "Duplicate CSV header"):
                load_records(path)

    def test_four_policy_regime(self):
        result = analyze_family(self.make_records("R1"), "R1")
        self.assertEqual((result["record_count"], result["matched_keys"]), (2160, 540))

    def test_cross_family_cohort_rejected(self):
        def contaminate(rows):
            for row in rows:
                row["cohort"] = row["cohort"].replace("C-", "R-", 1)
        with self.assertRaisesRegex(AuditError, "cross-family"):
            analyze_family(self.make_records("C", contaminate), "C")

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


    def test_no_tradeoff_crossing_is_null(self):
        def dominate(rows):
            for row in rows:
                if row["policy"] == "v3":
                    row["gross_water_m3"] = 90
        report = analyze_family(self.make_records("C", dominate), "C")
        self.assertIsNone(report["case_crossing_lambda_median"])
        self.assertEqual(report["comparisons"]["v3_dominates"], 540)

    def test_tradeoff_crossing_has_correct_unit_ratio(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertEqual(result["case_crossing_lambda_median"], 5.0)
        self.assertEqual(result["mean_loss_crossing_lambda"], 5.0)

    def test_path_level_output_has_twelve_complete_paths(self):
        result = analyze_family(self.make_records("C"), "C")
        effects = result["climate_path_effects"]
        self.assertEqual(len(effects), 12)
        self.assertEqual(sum(p["matched_keys"] for p in effects), 540)
        self.assertTrue(all(p["matched_keys"] == 45 for p in effects))
        self.assertTrue(all(p["mean_delta_water_m3"] == 10 for p in effects))
        self.assertTrue(all(p["mean_delta_q100"] == -2 for p in effects))

    def test_path_heterogeneity_is_not_hidden_by_global_mean(self):
        def different_one_path(rows):
            for row in rows:
                if row["seed"] == 1000 and row["policy"] == "v3":
                    row["gross_water_m3"] = 130
        result = analyze_family(self.make_records("C", different_one_path), "C")
        effects = result["climate_path_effects"]
        self.assertEqual(effects[0]["mean_delta_water_m3"], 30)
        self.assertTrue(all(p["mean_delta_water_m3"] == 10 for p in effects[1:]))
        self.assertAlmostEqual(result["mean_delta_water_m3"], 10 + 20 / 12)

    def test_pareto_partition_sums_to_matched_keys(self):
        result = analyze_family(self.make_records("C"), "C")
        counts = result["comparisons"]
        categories = ("v3_dominates", "v2_dominates", "both_tied",
                      "q_better_water_worse", "water_better_q_worse")
        self.assertEqual(sum(counts[c] for c in categories), 540)
        self.assertEqual(counts["water_better_q_worse"], 0)

    def test_reverse_tradeoff_category_detected(self):
        def reverse_tradeoff(rows):
            for row in rows:
                if row["policy"] == "v3":
                    row["gross_water_m3"] = 90
                    row["q_positive_plot_days"] = 12
                    row["below_98_plot_days"] = 11
        result = analyze_family(self.make_records("C", reverse_tradeoff), "C")
        self.assertEqual(result["comparisons"]["water_better_q_worse"], 540)
        self.assertEqual(result["comparisons"]["v3_dominates"], 0)

    def test_overlong_csv_record_rejected(self):
        row = next(rows_for_family("C"))
        text = ",".join(FIELDS) + "\\n" + ",".join(str(row[f]) for f in FIELDS) + ",extra\\n"
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "extra.csv"
            path.write_text(text.replace("\\n", "\n"), encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "extra CSV fields"):
                load_records(path)

    def test_empty_csv_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "empty.csv"
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "Missing CSV header"):
                load_records(path)

    def test_missing_required_metric_header_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "header.csv"
            path.write_text("cohort,policy\\n".replace("\\n", "\n"), encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "Missing columns"):
                load_records(path)

    def test_unknown_forecast_case_rejected(self):
        def change(rows):
            rows[0]["forecast_case"] = "oracle"
        with self.assertRaisesRegex(AuditError, "forecast case"):
            self.make_records("C", change)

    def test_unknown_climate_class_rejected(self):
        def change(rows):
            rows[0]["climate_class"] = "unknown"
        with self.assertRaisesRegex(AuditError, "climate class"):
            self.make_records("C", change)

    def test_unsupported_et_factor_rejected(self):
        def change(rows):
            rows[0]["et_forecast_multiplier"] = 1.5
        with self.assertRaisesRegex(AuditError, "ET factor"):
            self.make_records("C", change)

    def test_negative_water_rejected(self):
        def change(rows):
            rows[0]["gross_water_m3"] = -1
        with self.assertRaisesRegex(AuditError, "Water cap"):
            self.make_records("C", change)

    def test_negative_drainage_rejected(self):
        def change(rows):
            rows[0]["drainage_sum_mm"] = -1
        with self.assertRaisesRegex(AuditError, "Negative drainage"):
            self.make_records("C", change)

    def test_nonfinite_drainage_rejected(self):
        def change(rows):
            rows[0]["drainage_sum_mm"] = math.inf
        with self.assertRaisesRegex(AuditError, "Nonfinite"):
            self.make_records("C", change)

    def test_excessive_event_count_rejected(self):
        def change(rows):
            rows[0]["irrigation_events"] = 121
        with self.assertRaisesRegex(AuditError, "Invalid event or threshold count"):
            self.make_records("C", change)

    def test_threshold_count_order_rejected(self):
        def change(rows):
            rows[0]["q_positive_plot_days"] = 2
            rows[0]["below_98_plot_days"] = 3
        with self.assertRaisesRegex(AuditError, "Invalid event or threshold count"):
            self.make_records("C", change)

    def test_negative_q_count_rejected(self):
        def change(rows):
            rows[0]["q_positive_plot_days"] = -1
        with self.assertRaisesRegex(AuditError, "Invalid event or threshold count"):
            self.make_records("C", change)

    def test_missing_policy_label_rejected(self):
        def change(rows):
            rows[0]["policy"] = ""
        with self.assertRaisesRegex(AuditError, "Missing scenario/policy"):
            self.make_records("C", change)

    def test_unknown_policy_rejected(self):
        def change(rows):
            rows[0]["policy"] = "unknown_policy"
        with self.assertRaisesRegex(AuditError, "unexpected policy"):
            analyze_family(self.make_records("C", change), "C")

    def test_noninteger_seed_rejected(self):
        def change(rows):
            rows[0]["seed"] = "1.25"
        with self.assertRaisesRegex(AuditError, "Invalid count/seed"):
            self.make_records("C", change)

    def test_noninteger_event_count_rejected(self):
        def change(rows):
            rows[0]["irrigation_events"] = "1.5"
        with self.assertRaisesRegex(AuditError, "Invalid count/seed"):
            self.make_records("C", change)

    def test_manuscript_checkpoints_not_assumed_for_mock_data(self):
        result = analyze_family(self.make_records("C"), "C")
        with self.assertRaisesRegex(AuditError, "discrepancy"):
            verify_paper(result)

    def test_file_digest_is_exact_byte_sha256(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "bytes.bin"
            contents = b"abc\\x00".replace(b"\\x00", b"\x00")
            path.write_bytes(contents)
            self.assertEqual(file_sha256(path), hashlib.sha256(contents).hexdigest())

    def test_water_cap_boundary_is_accepted(self):
        def change(rows):
            for row in rows:
                row["gross_water_m3"] = 320
        result = analyze_family(self.make_records("C", change), "C")
        self.assertEqual(result["means"]["v2"]["water_m3"], 320)

    def test_undefined_crossing_fails_checkpoint_cleanly(self):
        def dominate(rows):
            for row in rows:
                if row["policy"] == "v3":
                    row["gross_water_m3"] = 90
        report = analyze_family(self.make_records("C", dominate), "C")
        self.assertIsNone(report["case_crossing_lambda_median"])
        with self.assertRaises(AuditError):
            verify_paper(report)

    def test_real_workbook_r_prefix_accepted(self):
        report = analyze_family(self.make_records("R1"), "R1")
        self.assertEqual(report["matched_keys"], 540)
        self.assertTrue(all(p["cohort"].startswith("R-")
                            for p in report["climate_path_effects"]))

    def test_incorrect_r1_prefix_rejected(self):
        def change(rows):
            for row in rows:
                row["cohort"] = row["cohort"].replace("R-", "R1-", 1)
        with self.assertRaisesRegex(AuditError, "cross-family"):
            analyze_family(self.make_records("R1", change), "R1")

    def test_climate_path_balance_rejects_skewed_classes(self):
        def skew_one_path(rows):
            for row in rows:
                if row["seed"] == 1008:
                    row["climate_class"] = "dry"
                    row["cohort"] = row["cohort"].replace("wet", "dry")
        with self.assertRaisesRegex(AuditError, "unbalanced climate paths"):
            analyze_family(self.make_records("C", skew_one_path), "C")

    def source_like_records(self, family):
        """Convert synthetic unit fixtures to the live source key identities."""
        records = self.make_records(family)
        index = {(cohort, climate): seed
                 for cohort, seed, climate in SOURCE_PATHS[family]}
        for row in records:
            cohort, _, climate, bias, et, forecast = row["key"]
            ordinal = int(cohort.rsplit("-", 1)[1]) % 4 + 1
            prefix = "C" if family == "C" else "R"
            authentic = f"{prefix}-{climate}-{ordinal}"
            row["key"] = (authentic, index[(authentic, climate)],
                          climate, bias, et, forecast)
        return records

    def paper_checkpoint_report(self, family):
        """Checkpoint *contract* only, never substitute for actual source replay."""
        e = EXPECTED[family]
        return {
            "family": family,
            "comparisons": {
                "q_lower": e["q_lower_tied_higher"][0],
                "q_tied": e["q_lower_tied_higher"][1],
                "q_higher": e["q_lower_tied_higher"][2],
                **{k: e[k] for k in ("higher_water", "v3_dominates",
                                     "v2_dominates", "both_tied",
                                     "q_better_water_worse")},
            },
            "mean_delta_water_m3": e["mean_delta_water"],
            "mean_delta_q100": e["mean_delta_q"],
            "case_crossing_lambda_median": e["crossing_median"],
            "weights": {str(w): {
                "v3": vals[0], "v2": vals[1], "tied": vals[2],
                "mean_delta_loss": vals[3],
            } for w, vals in EXPECTED_WEIGHT_GRID[family].items()},
        }

    def test_source_catalog_c_authentic_twelve_paths(self):
        records = self.source_like_records("C")
        verify_source_paths(records, "C")
        self.assertEqual(len(analyze_family(records, "C")["climate_path_effects"]), 12)

    def test_source_catalog_r_authentic_twelve_paths(self):
        records = self.source_like_records("R1")
        verify_source_paths(records, "R1")
        self.assertEqual(len(analyze_family(records, "R1")["climate_path_effects"]), 12)

    def test_source_catalog_rejects_modified_c_seed(self):
        records = self.source_like_records("C")
        key = records[0]["key"]
        records[0]["key"] = (key[0], key[1] + 1, *key[2:])
        with self.assertRaisesRegex(AuditError, "catalog mismatch"):
            verify_source_paths(records, "C")

    def test_source_catalog_rejects_modified_r_seed(self):
        records = self.source_like_records("R1")
        key = records[0]["key"]
        records[0]["key"] = (key[0], key[1] + 1, *key[2:])
        with self.assertRaisesRegex(AuditError, "catalog mismatch"):
            verify_source_paths(records, "R1")

    def test_source_catalog_rejects_renumbered_cohort(self):
        records = self.source_like_records("C")
        key = records[0]["key"]
        records[0]["key"] = ("C-dry-99", *key[1:])
        with self.assertRaisesRegex(AuditError, "catalog mismatch"):
            verify_source_paths(records, "C")

    def test_source_catalog_rejects_mislabeled_climate(self):
        records = self.source_like_records("R1")
        key = records[0]["key"]
        records[0]["key"] = (key[0], key[1], "wet", *key[3:])
        with self.assertRaisesRegex(AuditError, "catalog mismatch"):
            verify_source_paths(records, "R1")

    def test_source_catalog_rejects_unknown_family(self):
        with self.assertRaisesRegex(AuditError, "Unknown family"):
            verify_source_paths([], "unknown")

    def test_cohort_climate_conflict_rejected_c(self):
        def distort(rows):
            for row in rows:
                if row["cohort"] == "C-dry-0":
                    row["climate_class"] = "wet"
        with self.assertRaisesRegex(AuditError, "cohort climate class"):
            analyze_family(self.make_records("C", distort), "C")

    def test_cohort_climate_conflict_rejected_r(self):
        def distort(rows):
            for row in rows:
                if row["cohort"] == "R-medium-4":
                    row["climate_class"] = "dry"
        with self.assertRaisesRegex(AuditError, "cohort climate class"):
            analyze_family(self.make_records("R1", distort), "R1")

    def test_negative_prng_seed_rejected(self):
        def distort(rows):
            rows[0]["seed"] = -3
        with self.assertRaisesRegex(AuditError, "Negative synthetic weather seed"):
            self.make_records("C", distort)

    def test_three_classes_equal_key_denominators_c(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertEqual(set(result["climate_class_effects"]), {"dry", "medium", "wet"})
        self.assertTrue(all(r["matched_keys"] == 180 and r["climate_paths"] == 4
                            for r in result["climate_class_effects"].values()))
        self.assertTrue(all(r["mean_delta_q100"] == -2
                            for r in result["climate_class_effects"].values()))

    def test_three_classes_equal_key_denominators_r(self):
        result = analyze_family(self.make_records("R1"), "R1")
        self.assertEqual(sum(c["matched_keys"] for c in
                             result["climate_class_effects"].values()), 540)
        self.assertTrue(all(c["mean_delta_water_m3"] == 10 for c in
                            result["climate_class_effects"].values()))

    def test_single_path_heterogeneity_changes_only_its_class(self):
        def distort(rows):
            for row in rows:
                if row["seed"] == 1000 and row["policy"] == "v3":
                    row["gross_water_m3"] = 130
        result = analyze_family(self.make_records("C", distort), "C")
        self.assertAlmostEqual(result["climate_class_effects"]["dry"]["mean_delta_water_m3"], 15)
        for climate in ("medium", "wet"):
            self.assertAlmostEqual(result["climate_class_effects"][climate]["mean_delta_water_m3"], 10)

    def test_reference_checkpoint_contract_c_passes(self):
        verify_paper(self.paper_checkpoint_report("C"))

    def test_reference_checkpoint_contract_r_passes(self):
        verify_paper(self.paper_checkpoint_report("R1"))

    def test_all_eight_c_weight_counts_fail_closed_when_corrupted(self):
        for weight in EXPECTED_WEIGHT_GRID["C"]:
            with self.subTest(weight=weight):
                result = self.paper_checkpoint_report("C")
                result["weights"][str(weight)]["v2"] += 1
                with self.assertRaisesRegex(AuditError, f"lambda={weight} preference mismatch"):
                    verify_paper(result)

    def test_all_eight_r_weight_counts_fail_closed_when_corrupted(self):
        for weight in EXPECTED_WEIGHT_GRID["R1"]:
            with self.subTest(weight=weight):
                result = self.paper_checkpoint_report("R1")
                result["weights"][str(weight)]["tied"] += 1
                with self.assertRaisesRegex(AuditError, f"lambda={weight} preference mismatch"):
                    verify_paper(result)

    def test_all_eight_c_weight_means_fail_closed_when_corrupted(self):
        for weight in EXPECTED_WEIGHT_GRID["C"]:
            with self.subTest(weight=weight):
                result = self.paper_checkpoint_report("C")
                result["weights"][str(weight)]["mean_delta_loss"] += 1e-4
                with self.assertRaisesRegex(AuditError, f"lambda={weight} mean difference mismatch"):
                    verify_paper(result)

    def test_all_eight_r_weight_means_fail_closed_when_corrupted(self):
        for weight in EXPECTED_WEIGHT_GRID["R1"]:
            with self.subTest(weight=weight):
                result = self.paper_checkpoint_report("R1")
                result["weights"][str(weight)]["mean_delta_loss"] += 1e-4
                with self.assertRaisesRegex(AuditError, f"lambda={weight} mean difference mismatch"):
                    verify_paper(result)

    def test_nonfinite_manuscript_weight_is_rejected(self):
        result = self.paper_checkpoint_report("R1")
        result["weights"]["50"]["mean_delta_loss"] = math.nan
        with self.assertRaisesRegex(AuditError, "lambda=50 mean difference mismatch"):
            verify_paper(result)

    def test_source_catalog_cannot_be_inferred_from_toy_fixture(self):
        with self.assertRaisesRegex(AuditError, "catalog mismatch"):
            verify_source_paths(self.make_records("C"), "C")

    def test_water_median_and_range_are_descriptive_not_intervals(self):
        report = analyze_family(self.make_records("C"), "C")
        self.assertEqual(report["median_delta_water_m3"], 10)
        self.assertEqual(report["range_delta_water_m3"], [10, 10])

    def test_q_median_and_range_are_descriptive_not_intervals(self):
        report = analyze_family(self.make_records("C"), "C")
        self.assertEqual(report["median_delta_q100"], -2)
        self.assertEqual(report["range_delta_q100"], [-2, -2])

    def test_even_sample_median_uses_both_middle_scenario_values(self):
        def split(rows):
            changed = 0
            for row in rows:
                if row["policy"] == "v3":
                    if changed < 270:
                        row["gross_water_m3"] = 120
                    changed += 1
        report = analyze_family(self.make_records("C", split), "C")
        self.assertEqual(report["median_delta_water_m3"], 15)
        self.assertEqual(report["range_delta_water_m3"], [10, 20])

    def test_path_outlier_does_not_turn_median_into_mean(self):
        def inject(rows):
            for row in rows:
                if row["policy"] == "v3" and row["seed"] == 1000:
                    row["gross_water_m3"] = 130
        report = analyze_family(self.make_records("C", inject), "C")
        self.assertAlmostEqual(report["mean_delta_water_m3"], 10+20/12)
        self.assertEqual(report["median_delta_water_m3"], 10)
        self.assertEqual(report["range_delta_water_m3"], [10, 30])

    def test_r1_paired_medians_and_extrema_have_defined_units(self):
        report = analyze_family(self.make_records("R1"), "R1")
        self.assertEqual(report["median_delta_water_m3"], 10)
        self.assertEqual(report["median_delta_q100"], -2)
        self.assertEqual(report["range_delta_q100"], [-2, -2])

    def test_r1_reports_twelve_climate_paths(self):
        report = analyze_family(self.make_records("R1"), "R1")
        self.assertEqual(len(report["climate_path_effects"]), 12)
        self.assertEqual(sum(p["matched_keys"] for p in report["climate_path_effects"]), 540)


    def test_supplementary_q98_mean_matches_fixture(self):
        report = analyze_family(self.make_records("C"), "C")
        self.assertEqual(report["supplementary_paired_outcomes"]["below_98_plot_days"]["mean_delta"], -2)

    def test_supplementary_q98_median_matches_fixture(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertEqual(result["supplementary_paired_outcomes"]["below_98_plot_days"]["median_delta"], -2)

    def test_supplementary_q98_range_matches_fixture(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertEqual(result["supplementary_paired_outcomes"]["below_98_plot_days"]["range_delta"], [-2, -2])

    def test_supplementary_event_mean_is_not_water_mean(self):
        report = analyze_family(self.make_records("C"), "C")
        self.assertEqual(report["supplementary_paired_outcomes"]["irrigation_events"]["mean_delta"], 0)
        self.assertEqual(report["mean_delta_water_m3"], 10)

    def test_supplementary_drainage_mean_zero_fixture(self):
        report = analyze_family(self.make_records("C"), "C")
        self.assertEqual(report["supplementary_paired_outcomes"]["drainage_sum_mm"]["mean_delta"], 0)

    def test_supplementary_drainage_is_depth_not_volume(self):
        result = analyze_family(self.make_records("C"), "C")
        info = result["supplementary_paired_outcomes"]["drainage_sum_mm"]
        self.assertIn("mm", info["unit"])
        self.assertNotIn("m3", info["unit"])

    def test_supplementary_event_unit_is_event_count(self):
        report = analyze_family(self.make_records("C"), "C")
        self.assertIn("events", report["supplementary_paired_outcomes"]["irrigation_events"]["unit"])

    def test_supplementary_q98_is_not_crop_yield(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertIn("simulated", result["supplementary_paired_outcomes"]["below_98_plot_days"]["unit"])
        self.assertNotIn("yield", result["supplementary_paired_outcomes"]["below_98_plot_days"]["unit"])

    def test_supplementary_comparison_direction_explicit(self):
        result = analyze_family(self.make_records("C"), "C")
        for info in result["supplementary_paired_outcomes"].values():
            self.assertEqual(info["direction"], "v3 minus v2")

    def test_supplementary_denominators_are_540(self):
        result = analyze_family(self.make_records("C"), "C")
        for info in result["supplementary_paired_outcomes"].values():
            self.assertEqual(info["matched_keys"], 540)

    def test_supplementary_by_path_has_12_groups(self):
        result = analyze_family(self.make_records("R1"), "R1")
        for info in result["supplementary_paired_outcomes"].values():
            self.assertEqual(len(info["by_climate_path"]), 12)

    def test_supplementary_by_path_has_45_keys_each(self):
        result = analyze_family(self.make_records("C"), "C")
        for info in result["supplementary_paired_outcomes"].values():
            self.assertTrue(all(p["matched_keys"] == 45 for p in info["by_climate_path"]))

    def test_supplementary_by_class_has_180_keys(self):
        result = analyze_family(self.make_records("R1"), "R1")
        for info in result["supplementary_paired_outcomes"].values():
            self.assertEqual(set(info["by_climate_class"]), {"dry", "medium", "wet"})
            self.assertTrue(all(g["matched_keys"] == 180 for g in info["by_climate_class"].values()))

    def test_event_change_in_one_path_affects_global_mean(self):
        def perturb(rows):
            for row in rows:
                if row["seed"] == 1000 and row["policy"] == "v3":
                    row["irrigation_events"] = 10
        result = analyze_family(self.make_records("C", perturb), "C")
        info = result["supplementary_paired_outcomes"]["irrigation_events"]
        self.assertAlmostEqual(info["mean_delta"], 4 / 12)
        self.assertEqual(info["range_delta"], [0, 4])

    def test_event_change_in_one_path_is_visible_by_class(self):
        def perturb(rows):
            for row in rows:
                if row["seed"] == 1000 and row["policy"] == "v3":
                    row["irrigation_events"] = 10
        info = analyze_family(self.make_records("C", perturb), "C")["supplementary_paired_outcomes"]["irrigation_events"]
        self.assertEqual(info["by_climate_class"]["dry"]["mean_delta"], 1)
        self.assertEqual(info["by_climate_class"]["medium"]["mean_delta"], 0)
        self.assertEqual(info["by_climate_class"]["wet"]["mean_delta"], 0)

    def test_drainage_perturbation_preserves_mm_units(self):
        def perturb(rows):
            for row in rows:
                if row["climate_class"] == "wet" and row["policy"] == "v3":
                    row["drainage_sum_mm"] = 12.5
        info = analyze_family(self.make_records("C", perturb), "C")["supplementary_paired_outcomes"]["drainage_sum_mm"]
        self.assertAlmostEqual(info["mean_delta"], 12.5 / 3)
        self.assertEqual(info["by_climate_class"]["wet"]["mean_delta"], 12.5)
        self.assertEqual(info["by_climate_class"]["dry"]["mean_delta"], 0)

    def test_q98_strict_threshold_perturbation_remains_separate_from_q100(self):
        def perturb(rows):
            for row in rows:
                if row["policy"] == "v3":
                    row["below_98_plot_days"] = 8
        result = analyze_family(self.make_records("C", perturb), "C")
        self.assertEqual(result["supplementary_paired_outcomes"]["below_98_plot_days"]["mean_delta"], -1)
        self.assertEqual(result["mean_delta_q100"], -2)

    def test_leave_one_path_out_has_exactly_twelve_cases(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertEqual(len(result["leave_one_climate_path_out"]), 12)

    def test_leave_one_path_out_denominator_is_495(self):
        result = analyze_family(self.make_records("R1"), "R1")
        self.assertTrue(all(v["remaining_matched_keys"] == 495 for v in
                            result["leave_one_climate_path_out"]))

    def test_leave_one_path_out_is_homogeneous_for_constant_fixture(self):
        result = analyze_family(self.make_records("C"), "C")
        self.assertTrue(all(v["mean_delta_water_m3"] == 10 for v in
                            result["leave_one_climate_path_out"]))

    def test_leave_one_path_out_q100_is_homogeneous_for_constant_fixture(self):
        result = analyze_family(self.make_records("R1"), "R1")
        self.assertTrue(all(v["mean_delta_q100"] == -2 for v in
                            result["leave_one_climate_path_out"]))

    def test_leave_one_out_removes_high_water_path(self):
        def perturb(rows):
            for row in rows:
                if row["seed"] == 1000 and row["policy"] == "v3":
                    row["gross_water_m3"] = 130
        result = analyze_family(self.make_records("C", perturb), "C")
        excluded = next(v for v in result["leave_one_climate_path_out"]
                        if v["excluded_seed"] == 1000)
        self.assertAlmostEqual(excluded["mean_delta_water_m3"], 10)

    def test_leave_one_out_retains_effect_of_other_path_outlier(self):
        def perturb(rows):
            for row in rows:
                if row["seed"] == 1000 and row["policy"] == "v3":
                    row["gross_water_m3"] = 130
        result = analyze_family(self.make_records("C", perturb), "C")
        excluded = next(v for v in result["leave_one_climate_path_out"]
                        if v["excluded_seed"] == 1001)
        self.assertAlmostEqual(excluded["mean_delta_water_m3"], 10 + 20 / 11)

    def test_leave_one_out_removes_q100_path_outlier(self):
        def perturb(rows):
            for row in rows:
                if row["seed"] == 1000 and row["policy"] == "v3":
                    row["q_positive_plot_days"] = 4
                    row["below_98_plot_days"] = 4
        result = analyze_family(self.make_records("C", perturb), "C")
        excluded = next(v for v in result["leave_one_climate_path_out"]
                        if v["excluded_seed"] == 1000)
        self.assertAlmostEqual(excluded["mean_delta_q100"], -2)

    def test_leave_one_out_tracks_unique_path_ids(self):
        result = analyze_family(self.make_records("C"), "C")
        paths = {v["excluded_path"] for v in result["leave_one_climate_path_out"]}
        self.assertEqual(len(paths), 12)

    def test_supplementary_r1_four_policy_family_still_paired(self):
        result = analyze_family(self.make_records("R1"), "R1")
        self.assertEqual(result["record_count"], 2160)
        self.assertEqual(result["supplementary_paired_outcomes"]["irrigation_events"]["matched_keys"], 540)


    def test_frozen_hash_accepts_known_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            self.assertEqual(verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest(), 'C'), hashlib.sha256(b'abc').hexdigest())

    def test_frozen_hash_accepts_uppercase_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            self.assertEqual(verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest().upper(), 'C'), hashlib.sha256(b'abc').hexdigest())

    def test_frozen_hash_rejects_wrong_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, 'mismatch'): verify_frozen_sha256(path, '0'*64, 'C')

    def test_frozen_hash_rejects_empty_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, '', 'C')

    def test_frozen_hash_rejects_short_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, 'a'*63, 'C')

    def test_frozen_hash_rejects_long_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, 'a'*65, 'C')

    def test_frozen_hash_rejects_nonhex_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, 'z'*64, 'C')

    def test_frozen_hash_rejects_sha1_length(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, 'a'*40, 'C')

    def test_frozen_hash_rejects_embedded_whitespace(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, 'a'*32+' '+'a'*31, 'C')

    def test_frozen_hash_rejects_prefix(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, 'sha256:'+hashlib.sha256(b'abc').hexdigest(), 'C')

    def test_frozen_hash_rejects_newline(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '64 hexadecimal'): verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest()+'\n', 'C')

    def test_frozen_hash_rejects_mutated_bytes(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            path.write_bytes(b'abd')
                        with self.assertRaisesRegex(AuditError, 'mismatch'): verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest(), 'C')

    def test_frozen_hash_rejects_appended_bytes(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            path.write_bytes(b'abc\n')
                        with self.assertRaisesRegex(AuditError, 'mismatch'): verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest(), 'C')

    def test_frozen_hash_rejects_removed_bytes(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            path.write_bytes(b'ab')
                        with self.assertRaisesRegex(AuditError, 'mismatch'): verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest(), 'C')

    def test_frozen_hash_rejects_utf8_bom_change(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            path.write_bytes(b'\xef\xbb\xbfabc')
                        with self.assertRaisesRegex(AuditError, 'mismatch'): verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest(), 'C')

    def test_frozen_hash_rejects_case_changed_data(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            path.write_bytes(b'ABC')
                        with self.assertRaisesRegex(AuditError, 'mismatch'): verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest(), 'C')

    def test_frozen_hash_reports_family_label(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(AuditError, '^R1: frozen source SHA-256 mismatch'): verify_frozen_sha256(path, '0'*64, 'R1')

    def test_frozen_hash_handles_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            path.unlink()
                        with self.assertRaises(FileNotFoundError): verify_frozen_sha256(path, hashlib.sha256(b'abc').hexdigest(), 'C')

    def test_frozen_hash_digest_is_exact_bytes(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            self.assertEqual(file_sha256(path), hashlib.sha256(b'abc').hexdigest())

    def test_frozen_hash_rejects_numeric_digest(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "frozen.csv"
            path.write_bytes(b"abc")
            with self.assertRaises((TypeError, AttributeError)): verify_frozen_sha256(path, 123, 'C')



if __name__ == "__main__":
    unittest.main()
