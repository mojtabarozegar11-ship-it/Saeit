"""End-to-end offline CSV-free educational budget report safety contracts."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from .farm_enterprise_budget import FarmBudgetError
from .farm_enterprise_report_cli import build_report, main, read_scenario


def scenario(name="baseline"):
    return dict(
        scenario_id=name, crop_id="sample_crop", season_id="season_2026",
        currency="TOMAN", provenance="planning_assumption",
        area_ha="2", yield_kg_per_ha="4000", farmgate_price_per_kg="0.5",
        irrigation_m3_per_ha="3000", water_cost_per_m3="0.1",
        energy_kwh_per_ha="400", energy_cost_per_kwh="0.2",
        other_variable_cost_per_ha="1000", allocated_fixed_cost_per_ha="400",
    )


class OfflineFarmBudgetReportCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.first = self.root / "baseline.json"
        self.first.write_text(json.dumps(scenario()), encoding="utf-8")

    def save(self, data, name):
        target = self.root / name
        target.write_text(json.dumps(data), encoding="utf-8")
        return target

    def test_single_scenario_produces_usable_budget_not_paid_order(self):
        result = build_report(self.first)
        self.assertEqual(result["baseline"]["per_ha_and_total"]["gross_margin_per_ha"],
                         "620.000000")
        self.assertFalse(result["payment_collected"])
        self.assertFalse(result["publication_allowed"])

    def test_second_scenario_changes_report_without_claiming_real_savings(self):
        other = scenario("alternative")
        other["irrigation_m3_per_ha"] = "2500"
        other["yield_kg_per_ha"] = "4200"
        second = self.save(other, "alternative.json")
        result = build_report(self.first, second)
        self.assertEqual(result["comparison"]["differences_alternative_minus_baseline"]
                         ["delta_water_m3_per_ha"], "-500.000000")
        self.assertFalse(result["comparison"]["field_water_savings_verified"])

    def test_cli_main_writes_parseable_json_without_side_effects(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = main(["--baseline", str(self.first)])
        self.assertEqual(status, 0)
        result = json.loads(out.getvalue())
        self.assertFalse(result["payment_collected"])
        self.assertEqual(result["baseline"]["currency"], "TOMAN")

    def test_unexpected_field_is_not_silently_accepted(self):
        data = scenario()
        data["payment_verified"] = True
        path = self.save(data, "bad.json")
        with self.assertRaises(FarmBudgetError):
            read_scenario(path)

    def test_missing_cost_field_is_not_silently_zero(self):
        data = scenario()
        del data["energy_cost_per_kwh"]
        path = self.save(data, "missing.json")
        with self.assertRaises(FarmBudgetError):
            read_scenario(path)

    def test_duplicate_buyer_json_field_is_rejected(self):
        raw = self.first.read_text("utf-8")
        altered = raw.replace('"currency": "TOMAN"',
                              '"currency": "TOMAN", "currency": "USD"')
        path = self.root / "duplicate.json"
        path.write_text(altered, encoding="utf-8")
        with self.assertRaises(FarmBudgetError):
            read_scenario(path)

    def test_nonfinite_json_amount_is_rejected(self):
        path = self.root / "nan.json"
        path.write_text(self.first.read_text("utf-8").replace(
            '"area_ha": "2"', '"area_ha": NaN'), encoding="utf-8")
        with self.assertRaises(FarmBudgetError):
            read_scenario(path)

    def test_oversized_json_is_rejected_before_parser(self):
        path = self.root / "large.json"
        path.write_bytes(b" " * 33000)
        with self.assertRaises(FarmBudgetError):
            read_scenario(path)

    def test_empty_input_is_rejected(self):
        path = self.root / "empty.json"
        path.write_bytes(b"")
        with self.assertRaises(FarmBudgetError):
            read_scenario(path)

    def test_symlink_to_other_file_is_not_read(self):
        link = self.root / "link.json"
        link.symlink_to(self.first)
        with self.assertRaises(FarmBudgetError):
            read_scenario(link)

    def test_directory_path_is_not_valid_input_file(self):
        with self.assertRaises(FarmBudgetError):
            read_scenario(self.root)

    def test_incompatible_crop_is_not_combined_with_one_budget(self):
        wrong = scenario("alternative")
        wrong["crop_id"] = "different_crop"
        path = self.save(wrong, "incomparable.json")
        with self.assertRaises(FarmBudgetError):
            build_report(self.first, path)

    def test_cli_errors_do_not_disclose_user_filename_or_contents(self):
        bad = self.root / "secret-farm-invoice-2026.json"
        bad.write_bytes(b"{INVALID JSON")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(["--baseline", str(bad)])
        self.assertEqual(status, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertNotIn(bad.name, err.getvalue())
        self.assertNotIn("INVALID JSON", err.getvalue())
        self.assertEqual(json.loads(err.getvalue())["error"], "scenario_preflight_failed")

    def test_float_literal_is_preserved_without_binary_rounding(self):
        raw = self.first.read_text("utf-8").replace('"water_cost_per_m3": "0.1"',
                                                     '"water_cost_per_m3": 0.1')
        path = self.root / "exact-decimal-literal.json"
        path.write_text(raw, encoding="utf-8")
        report = build_report(path)
        self.assertEqual(report["baseline"]["per_ha_and_total"]["irrigation_cost_per_ha"],
                         "300.000000")

    def test_null_and_infinite_numeric_json_do_not_generate_outputs(self):
        for raw_value in ("null", "Infinity", "1e309", "-1"):
            with self.subTest(value=raw_value):
                original = self.first.read_text("utf-8")
                path = self.root / "invalid-num.json"
                path.write_text(original.replace('"area_ha": "2"',
                                                 '"area_ha": ' + raw_value), encoding="utf-8")
                with self.assertRaises(FarmBudgetError):
                    read_scenario(path)

    def test_report_digest_matches_same_local_source_replay(self):
        one = build_report(self.first)
        two = build_report(self.first)
        self.assertEqual(one["baseline"]["input_digest_sha256"],
                         two["baseline"]["input_digest_sha256"])


if __name__ == "__main__":
    unittest.main()
