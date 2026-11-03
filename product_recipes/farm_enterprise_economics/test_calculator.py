"""Executable tests for the standalone agricultural unit-economics tool."""
import json
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calculator import enterprise, evaluate, render_html_report


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

    def test_mississippi_state_extension_2020_greenhouse_enterprise_budget(self):
        """Cross-check contribution and break-even against an external budget.

        Source: https://extension.msstate.edu/publications/greenhouse-tomato-budgets-for-mississippi
        Historical 2020 arithmetic reference only, not current prices or a
        production recommendation.
        """
        from decimal import Decimal
        cases = (
            ("spring", 8000, "0.96", 3640, 4036, "0.96", "4.00"),
            ("fall", 6000, "1.00", 2936, 3044, "1.00", "20.00"),
            ("continuous", 14000, "0.92", 5828, 7080, "0.93", "-28.00"),
        )
        for name, units, price, direct, fixed, expected_break_even, expected_profit in cases:
            with self.subTest(crop_case=name):
                row = enterprise({
                    "name": name, "units_sold": units, "unit_price": price,
                    "variable_cost_per_unit": str(Decimal(direct) / Decimal(units)),
                    "allocated_fixed_cost": fixed,
                })
                self.assertEqual(row["break_even_unit_price_at_planned_volume"], expected_break_even)
                self.assertEqual(row["operating_profit"], expected_profit)
                self.assertGreaterEqual(
                    Decimal(row["break_even_unit_price_at_planned_volume"])
                    * Decimal(units), Decimal(direct + fixed))
                self.assertEqual(row["break_even_unit_price_at_planned_volume"],
                                 str((Decimal(direct + fixed) / Decimal(units)).quantize(
                                     Decimal("0.01"), rounding=__import__("decimal").ROUND_CEILING)))
        result = evaluate(self.example)
        self.assertEqual(result["accounting_scope"],
                         "contribution_profit_before_depreciation_financing_tax")
        self.assertFalse(result["input_values_independently_validated"])

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

    def test_portfolio_rounds_once_after_aggregating_subcent_enterprises(self):
        # Rounding each enterprise first would incorrectly turn both the
        # portfolio's revenue and operating profit into zero.
        row = {
            "units_sold": "1",
            "unit_price": "0.005",
            "variable_cost_per_unit": "0.001",
            "allocated_fixed_cost": "0.001",
            "selling_fee_percent": "0",
        }
        report = evaluate({"currency": "USD", "enterprises": [
            dict(row, name="Small unit A"),
            dict(row, name="Small unit B"),
        ]})
        self.assertEqual([r["sales_revenue"] for r in report["results"]],
                         ["0.00", "0.00"])
        self.assertEqual([r["operating_profit"] for r in report["results"]],
                         ["0.00", "0.00"])
        self.assertEqual(report["portfolio"], {
            "sales_revenue": "0.01",
            "total_cost": "0.00",
            "operating_profit": "0.01",
            "contribution_margin_total": "0.01",
        })
        base = next(row for row in report["portfolio_scenario_results"]
                    if row["volume_multiplier"] == "1.00"
                    and row["price_multiplier"] == "1.00")
        self.assertEqual(base["modeled_operating_profit"],
                         report["portfolio"]["operating_profit"])

    def test_rejects_invalid_inputs(self):
        bad = dict(self.example)
        bad["enterprises"] = [dict(self.example["enterprises"][0], units_sold=-1)]
        with self.assertRaises(ValueError):
            evaluate(bad)
        with self.assertRaises(ValueError):
            enterprise(dict(self.example["enterprises"][0], selling_fee_percent=105))
        with self.assertRaises(ValueError):
            enterprise(dict(self.example["enterprises"][0], unit_price="NaN"))

    def test_large_local_currency_portfolio_precision(self):
        # Farm budgets denominated in high-unit currencies must not fail
        # Decimal.quantize after multiplying independently bounded inputs.
        from decimal import Decimal
        row = {
            "name": "large-unit budget", "units_sold": "1e18",
            "unit_price": "1e18", "variable_cost_per_unit": "1e17",
            "allocated_fixed_cost": "1e18", "selling_fee_percent": "5",
        }
        data = {"currency": "IRR", "enterprises": [
            dict(row, name="Enterprise " + str(i)) for i in range(100)
        ]}
        result = evaluate(data)
        actual = Decimal(result["portfolio"]["sales_revenue"])
        self.assertEqual(actual, Decimal("1e38"))
        self.assertEqual(len(result["scenario_results"]), 900)
        self.assertGreater(Decimal(result["portfolio"]["operating_profit"]), 0)

    def test_invalid_extremes_fail_with_input_error(self):
        row = self.example["enterprises"][0]
        for value in ("1e21", "-1e21", "9" * 1000):
            with self.subTest(value=value[:20]):
                with self.assertRaises(ValueError):
                    enterprise(dict(row, unit_price=value))
        with self.assertRaises(ValueError):
            enterprise(dict(row, units_sold=float("inf")))
        with self.assertRaises(ValueError):
            enterprise(dict(row, units_sold="NaN"))

    def test_extreme_negative_decimal_exponents_are_bounded(self):
        """Short exponent notation must not expand into giant report strings."""
        original = self.example["enterprises"][0]
        for value in ("1e-25", "1e-1000000000", "9e-1000000000"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finer than supported"):
                    enterprise(dict(original, unit_price=value))
        # Zero with an enormous exponent is valid but must be canonicalized.
        zero = enterprise(dict(original, unit_price="0e-1000000000"))
        self.assertEqual(zero["unit_price_exact"], "0")
        self.assertEqual(zero["sales_revenue"], "0.00")
        self.assertEqual(zero["contribution_per_unit_exact"], "-4.00")
        edge = enterprise(dict(original, unit_price="1e-24"))
        self.assertEqual(edge["unit_price_exact"], "0.000000000000000000000001")

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


    def test_spreadsheet_formula_injection_is_rejected(self):
        original = self.example["enterprises"][0]
        for label in ("=HYPERLINK(\"https://example.com\")", "+SUM(1,1)",
                      "-1+2", "@SUM(1,1)", "＝1+2", "＋1+2",
                      "\t=1+2", " Farm\n=HYPERLINK(1)", "Farm\r@1"):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    enterprise(dict(original, name=label))
        safe = enterprise(dict(original, name="مزرعه زمرد ملل"))
        self.assertEqual(safe["name"], "مزرعه زمرد ملل")

    def test_csv_export_quotes_all_fields_and_preserves_safe_separators(self):
        import csv
        entry = dict(self.example["enterprises"][0], name='Farm "A", west')
        data = dict(self.example, enterprises=[entry])
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            inputs = home / "input.json"
            csvfile = home / "output.csv"
            inputs.write_text(json.dumps(data), encoding="utf8")
            finished = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("calculator.py")),
                 str(inputs), "--csv-output", str(csvfile)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(finished.returncode, 0, finished.stderr)
            raw = csvfile.read_text(encoding="utf8")
            self.assertTrue(raw.startswith('"enterprise","volume_multiplier"'))
            with csvfile.open(encoding="utf8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 9)
            self.assertTrue(all(row["enterprise"] == 'Farm "A", west' for row in rows))



    def test_portfolio_correlated_stress_is_not_single_enterprise_stress(self):
        second = {
            "name": "Field crop", "units_sold": 100,
            "unit_price": 20, "variable_cost_per_unit": 15,
            "allocated_fixed_cost": 100, "selling_fee_percent": 0,
        }
        result = evaluate(dict(self.example, enterprises=[
            self.example["enterprises"][0], second,
        ]))
        portfolio = result["portfolio_scenario_results"]
        self.assertEqual(len(portfolio), 9)
        base = next(x for x in portfolio if x["volume_multiplier"] == "1.00"
                    and x["price_multiplier"] == "1.00")
        self.assertEqual(base["modeled_operating_profit"], result["portfolio"]["operating_profit"])
        downside = next(x for x in portfolio if x["volume_multiplier"] == "0.80"
                        and x["price_multiplier"] == "0.90")
        self.assertEqual(downside["modeled_operating_profit"], "780.00")

    def test_offline_html_report_escapes_customer_labels(self):
        customer_name = "Orchard <script>alert(1)</script>"
        item = dict(self.example["enterprises"][0], name=customer_name)
        html = render_html_report(evaluate(dict(self.example, enterprises=[item])))
        self.assertIn("Orchard &lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("Whole-portfolio sensitivity", html)
        self.assertIn('name="viewport"', html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<iframe", html)

    def test_offline_html_cli_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            input_file = home / "inputs.json"
            report_file = home / "farm-report.html"
            input_file.write_text(json.dumps(self.example), encoding="utf8")
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("calculator.py")),
                 str(input_file), "--html-output", str(report_file)],
                text=True, capture_output=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = report_file.read_text(encoding="utf8")
            self.assertTrue(text.startswith("<!doctype html>"))
            self.assertIn("Illustrative orchard", text)


    def test_cli_protects_customer_input_and_distinct_report_destinations(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            input_file = base / "customer-input.json"
            output_file = base / "reports.json"
            original = json.dumps(self.example)
            input_file.write_text(original, encoding="utf8")
            unsafe_options = (
                ("--json-output", str(input_file)),
                ("--csv-output", str(input_file)),
                ("--html-output", str(input_file)),
                ("--json-output", str(output_file), "--csv-output", str(output_file)),
                ("--json-output", str(output_file), "--html-output", str(output_file)),
                ("--csv-output", str(output_file), "--html-output", str(output_file)),
            )
            for options in unsafe_options:
                with self.subTest(options=options):
                    proc = subprocess.run(
                        [sys.executable, str(Path(__file__).with_name("calculator.py")),
                         str(input_file), *options],
                        text=True, capture_output=True, timeout=15,
                    )
                    self.assertEqual(proc.returncode, 2, proc.stderr)
                    self.assertIn("must be distinct", proc.stderr)
                    self.assertEqual(input_file.read_text(encoding="utf8"), original)
                    self.assertFalse(output_file.exists())


    def test_subcent_unit_costs_remain_visible_without_changing_legacy_money_fields(self):
        """Commodity units can cost less than one hundredth of a currency unit."""
        fine_grained = {
            "name": "Grain grams", "units_sold": 10000,
            "unit_price": "0.005", "variable_cost_per_unit": "0.0035",
            "allocated_fixed_cost": "2", "selling_fee_percent": 0,
        }
        result = evaluate({"currency": "USD", "enterprises": [fine_grained]})
        entry = result["results"][0]
        self.assertEqual(result["version"], "1.3")
        self.assertEqual(entry["unit_price"], "0.00")  # Legacy cents-rounded field.
        self.assertEqual(entry["unit_price_exact"], "0.005")
        self.assertEqual(entry["variable_cost_per_unit_exact"], "0.0035")
        self.assertEqual(entry["contribution_per_unit_exact"], "0.0015")
        self.assertEqual(entry["break_even_unit_price_unrounded"], "0.0037")
        self.assertEqual(entry["sales_revenue"], "50.00")
        self.assertEqual(entry["operating_profit"], "13.00")
        self.assertEqual(entry["break_even_units"], 1334)
        page = render_html_report(result)
        self.assertIn("<td>0.005</td>", page)
        self.assertIn("<td>0.0035</td>", page)
        self.assertIn("<td>0.0015</td>", page)
        self.assertIn("rounded to 0.01", page)

    def test_unreachable_break_even_is_not_rendered_as_literal_none(self):
        entry = {
            "name": "Loss enterprise", "units_sold": 50, "unit_price": 3,
            "variable_cost_per_unit": 5, "allocated_fixed_cost": 100,
        }
        result = evaluate({"currency": "USD", "enterprises": [entry]})
        row = result["results"][0]
        self.assertIsNone(row["break_even_units"])
        self.assertEqual(row["break_even_unit_price_unrounded"], "7")
        html = render_html_report(result)
        self.assertIn("<td>N/A</td>", html)
        self.assertNotIn("<td>None</td>", html)


if __name__ == "__main__":
    unittest.main()
