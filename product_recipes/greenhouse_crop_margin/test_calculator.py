"""Functional tests for the greenhouse crop margin planning tool."""
import json
from decimal import Decimal
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

calculator_path = Path(__file__).resolve().with_name("calculator.py")
spec = importlib.util.spec_from_file_location("greenhouse_crop_margin_calculator", calculator_path)
calculator_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calculator_module)
calculate = calculator_module.calculate


class GreenhouseCropMarginTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "currency": "USD",
            "area_m2": 1000,
            "expected_yield_kg_per_m2": 12,
            "price_per_kg": 2.5,
            "variable_cost_per_m2": 15,
            "fixed_cost_total": 5000,
            "rejection_rate_percent": 10,
        }

    def test_margin_revenue_and_break_even(self):
        result = calculate(self.data)
        values = result["results"]
        self.assertEqual(values["gross_yield_kg"], "12000")
        self.assertEqual(values["saleable_yield_kg"], "10800.0")
        self.assertEqual(values["sales_revenue"], "27000.00")
        self.assertEqual(values["total_cost"], "20000.00")
        self.assertEqual(values["net_margin"], "7000.00")
        self.assertEqual(values["break_even_price_per_kg"], "1.86")

    def test_downside_stress_is_calculated_not_just_described(self):
        legacy = calculate(self.data)["results"]["downside_stress_test"]
        self.assertEqual(legacy["modeled_revenue"], "21870.00")
        self.assertEqual(legacy["modeled_total_cost"], "20000.00")
        self.assertEqual(legacy["modeled_net_margin"], "1870.00")
        self.assertIsNone(legacy["water_tariff_multiplier"])
        resource = calculate(self.complete_resource_case())["results"]["downside_stress_test"]
        self.assertEqual(resource["modeled_revenue"], "21870.00")
        self.assertEqual(resource["modeled_total_cost"], "20200.00")
        self.assertEqual(resource["modeled_net_margin"], "1670.00")
        self.assertTrue(resource["water_tariff_scenario_applicable"])
        self.assertFalse(resource["market_probability_calibrated"])
        loss = calculate(dict(self.data, price_per_kg="0.5"))["results"]["downside_stress_test"]
        self.assertTrue(loss["modeled_loss"])

    def test_break_even_thresholds_are_not_rounded_below_true_minimum(self):
        result = calculate(self.data)["results"]
        price = Decimal(result["break_even_price_per_kg"])
        required_yield = Decimal(result["minimum_gross_yield_kg_per_m2_to_break_even"])
        self.assertEqual(str(required_yield), "8.889")
        self.assertTrue(result["minimum_gross_yield_reachable"])
        saleable_kg = Decimal(result["saleable_yield_kg"])
        total_cost = Decimal(result["total_cost"])
        self.assertGreaterEqual(price * saleable_kg, total_cost)
        self.assertLess((price - Decimal("0.01")) * saleable_kg, total_cost)
        revenue_at_threshold = (
            Decimal(self.data["area_m2"]) * required_yield
            * (Decimal(1) - Decimal("0.1")) * Decimal("2.5")
        )
        self.assertGreaterEqual(revenue_at_threshold, total_cost)
        self.assertLess(revenue_at_threshold - Decimal("0.001") * Decimal("1000") * Decimal("0.9") * Decimal("2.5"),
                        total_cost)

    def test_unreachable_threshold_and_no_cost_edge_cases(self):
        for changes in ({"price_per_kg": 0}, {"rejection_rate_percent": 100}):
            with self.subTest(changes=changes):
                result = calculate(dict(self.data, **changes))["results"]
                self.assertIsNone(result["minimum_gross_yield_kg_per_m2_to_break_even"])
                self.assertFalse(result["minimum_gross_yield_reachable"])
        zero_cost = calculate(dict(self.data, price_per_kg=0,
                                   variable_cost_per_m2=0,
                                   fixed_cost_total=0))["results"]
        self.assertEqual(zero_cost["minimum_gross_yield_kg_per_m2_to_break_even"],
                         "0.000")
        self.assertTrue(zero_cost["minimum_gross_yield_reachable"])

    def test_zero_saleable_yield_has_no_break_even_price(self):
        result = calculate(dict(self.data, rejection_rate_percent=100))
        self.assertFalse(result["results"]["break_even_reachable"])
        self.assertIsNone(result["results"]["break_even_price_per_kg"])

    def test_rejects_invalid_numeric_inputs(self):
        for field, value in (("area_m2", 0), ("price_per_kg", -1),
                             ("rejection_rate_percent", 101),
                             ("expected_yield_kg_per_m2", "NaN")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                calculate(dict(self.data, **{field: value}))

    def complete_resource_case(self):
        # All rates and volumes are hypotheses supplied by the user.
        return {
            "currency": "USD", "area_m2": 1000,
            "expected_yield_kg_per_m2": 12, "price_per_kg": 2.5,
            "fixed_cost_total": 5000, "rejection_rate_percent": 10,
            "crop": "tomato", "season": "spring 2026",
            "water_liters_per_m2": 100, "water_cost_per_liter": 0.01,
            "energy_kwh_per_m2": 10, "energy_cost_per_kwh": 0.2,
            "labor_hours_per_m2": 0.5, "labor_cost_per_hour": 8,
            "climate_control_kwh_per_m2": 5,
            "climate_control_cost_per_kwh": 0.2,
            "other_variable_cost_per_m2": 7,
        }

    def test_explicit_cost_drivers_and_crop_season(self):
        result = calculate(self.complete_resource_case())
        self.assertEqual(result["version"], "2.1")
        self.assertEqual(result["model_scope"], "resource_explicit_uncalibrated")
        self.assertFalse(result["market_data_independently_validated"])
        self.assertEqual(result["inputs"]["crop"], "tomato")
        self.assertEqual(result["inputs"]["season"], "spring 2026")
        self.assertEqual(result["results"]["resource_cost_breakdown"], {
            "water": "1000.00", "energy": "2000.00", "labor": "4000.00",
            "climate_control": "1000.00", "other": "7000.00",
        })
        self.assertEqual(result["results"]["net_margin"], "7000.00")
        self.assertEqual(result["results"]["break_even_price_per_kg"], "1.86")

    def test_prevent_double_counting_and_partial_resource_claims(self):
        inputs = self.complete_resource_case()
        with self.assertRaisesRegex(ValueError, "double counting"):
            calculate(dict(inputs, variable_cost_per_m2=15))
        missing = dict(inputs)
        del missing["water_liters_per_m2"]
        with self.assertRaisesRegex(ValueError, "requires all fields"):
            calculate(missing)
        with self.assertRaises(ValueError):
            calculate(dict(inputs, season="\nnot valid"))

    def test_seeded_uncertainty_is_reproducible_but_uncalibrated(self):
        case = self.complete_resource_case()
        case["uncertainty"] = {
            "yield_min_kg_per_m2": 8,
            "yield_max_kg_per_m2": 16,
            "price_min_per_kg": 2,
            "price_max_per_kg": 3,
            "seed": 921,
        }
        first = calculate(case)["results"]["uncertainty"]
        second = calculate(case)["results"]["uncertainty"]
        self.assertEqual(first, second)
        self.assertEqual(first["sample_count"], 2000)
        self.assertFalse(first["uncertainty_inputs_market_calibrated"])
        self.assertLess(float(first["p05_net_margin"]), float(first["p95_net_margin"]))

    def test_invalid_uncertainty_and_legacy_risk_block(self):
        case = self.complete_resource_case()
        risk = {"yield_min_kg_per_m2": 13, "yield_max_kg_per_m2": 16,
                "price_min_per_kg": 2, "price_max_per_kg": 3}
        with self.assertRaisesRegex(ValueError, "triangular mode"):
            calculate(dict(case, uncertainty=risk))
        with self.assertRaisesRegex(ValueError, "bounded non-negative"):
            calculate(dict(case, uncertainty=dict(risk, yield_min_kg_per_m2=8, seed=True)))
        with self.assertRaisesRegex(ValueError, "complete explicit"):
            calculate(dict(self.data, uncertainty={})) 

    def test_cli_reads_input_and_writes_json(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "input.json"
            target = Path(root) / "result.json"
            source.write_text(json.dumps(self.data), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("calculator.py")),
                 str(source), "--json-output", str(target)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["results"]["net_margin"],
                             "7000.00")


if __name__ == "__main__":
    unittest.main()
