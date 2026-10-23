"""Executable tests for the standalone agricultural unit-economics tool."""
import json
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calculator import enterprise, evaluate


class EconomicsTests(unittest.TestCase):
    def setUp(self):
        self.example = {
            "currency": "USD",
            "enterprises": [{
                "name": "Illustrative orchard",
                "units_sold": 1000,
                "unit_price": 10,
                "variable_cost_per_unit": 4,
                "allocated_fixed_cost": 3000,
                "selling_fee_percent": 5,
            }],
        }

    def test_break_even_and_totals(self):
        result = evaluate(self.example)
        row = result["results"][0]
        self.assertEqual(row["sales_revenue"], "10000.00")
        self.assertEqual(row["selling_fees"], "500.00")
        self.assertEqual(row["total_cost"], "7500.00")
        self.assertEqual(row["contribution_per_unit"], "5.50")
        self.assertEqual(row["operating_profit"], "2500.00")
        self.assertEqual(row["break_even_units"], 546)
        self.assertEqual(len(result["scenario_results"]), 9)

    def test_break_even_price_and_margin_of_safety(self):
        row = evaluate(self.example)["results"][0]
        self.assertEqual(row["break_even_unit_price_at_planned_volume"], "7.37")
        self.assertEqual(row["margin_of_safety_units"], "454")
        self.assertEqual(row["margin_of_safety_percent"], "45.40")
        # The displayed break-even threshold is rounded *up*, never down.
        from decimal import Decimal
        self.assertGreaterEqual(Decimal(row["break_even_unit_price_at_planned_volume"]) * Decimal("0.95"),
                                Decimal("4") + Decimal("3000") / Decimal("1000"))
        zero = enterprise(dict(self.example["enterprises"][0], units_sold=0))
        self.assertIsNone(zero["break_even_unit_price_at_planned_volume"])
        self.assertIsNone(zero["margin_of_safety_percent"])
        full_fee = enterprise(dict(self.example["enterprises"][0], selling_fee_percent=100))
        self.assertIsNone(full_fee["break_even_unit_price_at_planned_volume"])
        self.assertIsNone(full_fee["margin_of_safety_units"])

    def test_negative_contribution_has_no_break_even(self):
        row = enterprise({
            "name": "Loss-making", "units_sold": 50, "unit_price": 3,
            "variable_cost_per_unit": 5, "allocated_fixed_cost": 100
        })
        self.assertFalse(row["break_even_reachable"])
        self.assertIsNone(row["break_even_units"])
        self.assertEqual(row["operating_profit"], "-200.00")

    def test_scenario_range(self):
        r = evaluate(self.example)
        outcomes = [float(x["modeled_operating_profit"]) for x in r["scenario_results"]]
        self.assertLess(min(outcomes), 2500)
        self.assertGreater(max(outcomes), 2500)

    def test_portfolio_aggregation_without_double_fixed_costs(self):
        data = dict(self.example)
        data["enterprises"] = self.example["enterprises"] + [{
            "name": "Another illustration", "units_sold": 0, "unit_price": 4,
            "variable_cost_per_unit": 2, "allocated_fixed_cost": 100
        }]
        result = evaluate(data)
        self.assertEqual(result["portfolio"]["operating_profit"], "2400.00")
        self.assertEqual(len(result["scenario_results"]), 18)

    def test_rejects_invalid_inputs(self):
        bad = dict(self.example)
        bad["enterprises"] = [dict(self.example["enterprises"][0], units_sold=-1)]
        with self.assertRaises(ValueError):
            evaluate(bad)
        with self.assertRaises(ValueError):
            enterprise(dict(self.example["enterprises"][0], selling_fee_percent=105))
        with self.assertRaises(ValueError):
            enterprise(dict(self.example["enterprises"][0], unit_price="NaN"))

    def test_duplicate_enterprise_names_rejected(self):
        bad = dict(self.example)
        bad["enterprises"] = self.example["enterprises"] * 2
        with self.assertRaises(ValueError):
            evaluate(bad)

    def test_real_cli_json_and_csv(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "input.json"
            js = Path(root) / "results.json"
            csv = Path(root) / "scenarios.csv"
            src.write_text(json.dumps(self.example), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("calculator.py")), str(src),
                 "--json-output", str(js), "--csv-output", str(csv)],
                capture_output=True, text=True, timeout=15
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(js.read_text(encoding="utf-8"))["portfolio"]["operating_profit"], "2500.00")
            self.assertEqual(len(csv.read_text(encoding="utf-8").splitlines()), 10)


if __name__ == "__main__":
    unittest.main()
