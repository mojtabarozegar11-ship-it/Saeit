"""Deterministic QA for a genuine new finance decision MVP; no production use."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "product_prototypes" / "orchard_decision_audit"
SPEC = importlib.util.spec_from_file_location(
    "astra_orchard_decision_engine_tests", PROTOTYPE / "decision_audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def scenario():
    return json.loads((PROTOTYPE / "example_synthetic.json").read_text(encoding="utf-8"))


def rows(data, scenario_key="base"):
    return {r["option"]: r for r in data["scenarios"][scenario_key]}


class OrchardInvestmentDecisionAuditTests(unittest.TestCase):
    def test_baseline_npv_known_independent_formula(self):
        report = audit.analyze(scenario())
        v = rows(report)
        expected_keep = sum(Decimal(40) / (Decimal("1.1") ** y) for y in (1, 2, 3))
        expected_replace = Decimal(-100) + sum(
            Decimal(90) / (Decimal("1.1") ** y) for y in (1, 2, 3))
        self.assertEqual(Decimal(v["Maintain Existing Trees"]["npv"]),
                         expected_keep.quantize(Decimal(".01")))
        self.assertEqual(Decimal(v["Replace Orchard Block"]["npv"]),
                         expected_replace.quantize(Decimal(".01")))
        self.assertEqual(report["leading_option_by_base_npv_not_advice"],
                         "Replace Orchard Block")

    def test_base_delta_to_reference_correct(self):
        results = rows(audit.analyze(scenario()))
        self.assertEqual(results["Maintain Existing Trees"]["delta_npv_vs_reference"], "0.00")
        self.assertGreater(Decimal(results["Replace Orchard Block"]["delta_npv_vs_reference"]), 0)

    def test_discount_rate_zero_no_double_count_investment(self):
        s = scenario()
        s["discount_rate_pct"] = "0"
        r = rows(audit.analyze(s))
        self.assertEqual(r["Maintain Existing Trees"]["npv"], "120.00")
        self.assertEqual(r["Replace Orchard Block"]["npv"], "170.00")
        self.assertEqual(r["Replace Orchard Block"]["years"][0]["cashflow"], "-100.00")

    def test_downside_reverses_preferred_decision_with_explicit_stress(self):
        report = audit.analyze(scenario())
        base = report["scenarios"]["base"][0]["option"]
        downside = report["scenarios"]["downside"][0]["option"]
        self.assertEqual(base, "Replace Orchard Block")
        self.assertEqual(downside, "Maintain Existing Trees")
        r = rows(report, "downside")
        self.assertEqual(r["Maintain Existing Trees"]["years"][1]["cashflow"], "6.00")
        self.assertEqual(r["Replace Orchard Block"]["years"][1]["cashflow"], "32.40")

    def test_upside_correct_price_times_yield_and_variable_cost_only(self):
        r = rows(audit.analyze(scenario()), "upside")
        self.assertEqual(r["Maintain Existing Trees"]["years"][1]["stressed_revenue"], "121.00")
        self.assertEqual(r["Maintain Existing Trees"]["years"][1]["stressed_variable_cost"], "27.00")
        self.assertEqual(r["Maintain Existing Trees"]["years"][1]["cashflow"], "64.00")
        self.assertEqual(r["Replace Orchard Block"]["years"][1]["cashflow"], "130.70")

    def test_breakeven_multiplier_matches_zero_npv_definition(self):
        r = rows(audit.analyze(scenario()))
        expected = (
            Decimal("100") + Decimal("80") *
            sum(1 / Decimal("1.1") ** y for y in (1, 2, 3))
        ) / (Decimal("170") * sum(1 / Decimal("1.1") ** y for y in (1, 2, 3)))
        self.assertEqual(r["Replace Orchard Block"]["breakeven_total_revenue_multiplier"],
                         str(expected.quantize(Decimal("0.0001"))))

    def test_breakeven_unknown_when_revenue_zero(self):
        s = scenario()
        for option in s["options"]:
            for year in option["years"]:
                year["revenue"] = "0"
        r = rows(audit.analyze(s))
        self.assertIsNone(r["Replace Orchard Block"]["breakeven_total_revenue_multiplier"])

    def test_negative_npvs_are_not_misrepresented(self):
        s = scenario()
        for o in s["options"]:
            for row in o["years"][1:]:
                row["revenue"] = "0"
        report = audit.analyze(s)
        self.assertTrue(report["all_base_npvs_negative"])
        self.assertFalse(report["commercial_quality_verified"])
        self.assertFalse(report["store_listing_authorized"])
        self.assertFalse(report["market_demand_verified"])

    def test_reference_name_must_exist(self):
        s = scenario()
        s["reference_option"] = "Not present"
        with self.assertRaisesRegex(audit.InputError, "reference_option"):
            audit.analyze(s)

    def test_duplicate_options_and_missing_years_rejected(self):
        s = scenario()
        s["options"][1]["name"] = s["options"][0]["name"]
        with self.assertRaisesRegex(audit.InputError, "distinct"):
            audit.analyze(s)
        s = scenario()
        s["options"][1]["years"].pop()
        with self.assertRaisesRegex(audit.InputError, "exactly"):
            audit.analyze(s)

    def test_nonsequential_year_and_additional_fields_blocked(self):
        s = scenario()
        s["options"][1]["years"][1]["year"] = 2
        with self.assertRaisesRegex(audit.InputError, "sequence"):
            audit.analyze(s)
        s = scenario()
        s["options"][0]["years"][1]["untrusted_extra"] = 123
        with self.assertRaisesRegex(audit.InputError, "exactly"):
            audit.analyze(s)

    def test_negative_nonfinite_float_bool_overlimit_values_rejected(self):
        invalid = ("-1", "NaN", "Infinity", "1000000000000001", 1.1, True)
        for v in invalid:
            with self.subTest(v=v):
                s = scenario()
                s["options"][0]["years"][1]["revenue"] = v
                with self.assertRaises(audit.InputError):
                    audit.analyze(s)

    def test_units_and_rate_validation(self):
        for key, value in (
            ("currency", "USD,EUR"), ("currency", "usd"),
            ("unit", "acres_or_hectares"), ("money_basis", "automatic"),
            ("horizon_years", True), ("discount_rate_pct", "-0.01"),
            ("discount_rate_pct", "101"),
        ):
            with self.subTest(key=key, val=value):
                s = scenario()
                s[key] = value
                with self.assertRaises(audit.InputError):
                    audit.analyze(s)

    def test_stress_factor_must_be_explicit_and_bounded(self):
        s = scenario()
        s["stress_scenarios"].pop("downside")
        with self.assertRaisesRegex(audit.InputError, "downside"):
            audit.analyze(s)
        s = scenario()
        s["stress_scenarios"]["downside"]["price_factor"] = "-1"
        with self.assertRaises(audit.InputError):
            audit.analyze(s)
        s = scenario()
        s["stress_scenarios"]["upside"]["yield_factor"] = "100"
        with self.assertRaises(audit.InputError):
            audit.analyze(s)

    def test_unsourced_costs_are_flagged_not_auto_proven(self):
        s = scenario()
        s["assumptions"] = []
        r = audit.analyze(s)
        self.assertIn("UNSOURCED_INPUT:Replace Orchard Block:capital_cost", r["warnings"])
        self.assertIn("UNSOURCED_INPUT:Maintain Existing Trees:revenue", r["warnings"])
        self.assertFalse(r["sources_independently_verified"])

    def test_fake_record_label_never_proves_source(self):
        s = scenario()
        s["assumptions"][0]["evidence_status"] = "operator_record"
        r = audit.analyze(s)
        self.assertFalse(r["sources_independently_verified"])
        self.assertFalse(r["commercial_quality_verified"])

    def test_document_assumptions_are_required_to_have_known_categories(self):
        s = scenario()
        s["assumptions"][0]["field"] = "profit_guaranteed"
        with self.assertRaisesRegex(audit.InputError, "unknown"):
            audit.analyze(s)
        s = scenario()
        s["assumptions"][0]["source_reference"] = ""
        with self.assertRaisesRegex(audit.InputError, "source_reference"):
            audit.analyze(s)

    def test_unchanged_input_gives_identical_hash_and_report(self):
        s = scenario()
        original = deepcopy(s)
        r1 = audit.analyze(s)
        r2 = audit.analyze(deepcopy(s))
        self.assertEqual(r1, r2)
        self.assertEqual(s, original)
        self.assertEqual(len(r1["input_sha256"]), 64)

    def test_year_zero_salvage_variable_fixed_and_capital_dont_overlap(self):
        s = scenario()
        s["options"][1]["years"][0].update({
            "revenue": "0", "variable_cost": "5", "fixed_cost": "4",
            "capital_cost": "100", "terminal_value": "3"})
        y = rows(audit.analyze(s))["Replace Orchard Block"]["years"][0]
        self.assertEqual(y["cashflow"], "-106.00")
        self.assertEqual(y["discounted_cashflow"], "-106.00")

    def test_without_investment_must_warn_not_fabricate_payout(self):
        report = audit.analyze(scenario())
        self.assertIn("NO_YEAR_ZERO_CAPITAL_OUTLAY:Maintain Existing Trees", report["warnings"])
        self.assertTrue(report["all_base_npvs_negative"] is False)

    def test_cli_private_artifact_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home)
            source = root / "fixture.json"
            dest = root / "output.json"
            source.write_text(json.dumps(scenario()), encoding="utf-8")
            command = [sys.executable, str(PROTOTYPE / "decision_audit.py"),
                       "--input", str(source), "--out", str(dest)]
            p = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("ORCHARD_DECISION_AUDIT_STATUS=PRIVATE_REFERENCE_MVP", p.stdout)
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(dest.read_text())["new_public_product"], False)
            second = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(second.returncode, 0)
            source_bytes = source.read_bytes()
            p3 = subprocess.run(
                [sys.executable, str(PROTOTYPE / "decision_audit.py"),
                 "--input", str(source), "--out", str(source)],
                capture_output=True, text=True, timeout=15)
            self.assertNotEqual(p3.returncode, 0)
            self.assertEqual(source.read_bytes(), source_bytes)


if __name__ == "__main__":
    unittest.main()
