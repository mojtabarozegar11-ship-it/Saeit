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

    def test_contribution_and_operating_profit_margins_are_separate(self):
        row = evaluate(self.example)["results"][0]
        # Revenue 10,000; contribution 5,500; operating profit 2,500.
        self.assertEqual(row["contribution_margin_percent"], "55.00")
        self.assertEqual(row["operating_profit_margin_percent"], "25.00")
        zero = enterprise(dict(self.example["enterprises"][0], units_sold=0))
        self.assertIsNone(zero["contribution_margin_percent"])
        self.assertIsNone(zero["operating_profit_margin_percent"])
        loss = enterprise(dict(self.example["enterprises"][0],
                               unit_price=3, variable_cost_per_unit=5))
        self.assertEqual(loss["contribution_margin_percent"], "-71.67")
        self.assertEqual(loss["operating_profit_margin_percent"], "-171.67")

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

    def test_bidi_spoofing_and_unicode_line_injection_are_rejected(self):
        # A finance report must not allow hidden character reordering in labels.
        bad_names = (
            "Wheat\u202e=500", "Crop\u2028=HYPERLINK(1,2)",
            "Rice\u2066secret\u2069", "Tomato\u200fFake",
            "Potato\u061cNote", "Olive\u2029NextRow",
        )
        for name in bad_names:
            with self.subTest(name=repr(name)):
                with self.assertRaises(ValueError):
                    enterprise(dict(self.example["enterprises"][0], name=name))
        good = enterprise(dict(self.example["enterprises"][0],
                               name="گندم\u200cدیم"))
        self.assertEqual(good["name"], "گندم\u200cدیم")

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

    def test_portfolio_profit_percentages_use_revenue_weights(self):
        source = {
            "currency": "USD",
            "enterprises": [
                dict(self.example["enterprises"][0]),
                {"name": "Smaller market crop",
                 "units_sold": 50, "unit_price": 100,
                 "variable_cost_per_unit": 20,
                 "allocated_fixed_cost": 1000},
            ],
        }
        result = evaluate(source)
        portfolio = result["portfolio"]
        self.assertEqual(portfolio["sales_revenue"], "15000.00")
        self.assertEqual(portfolio["contribution_margin_total"], "9500.00")
        self.assertEqual(portfolio["operating_profit"], "5500.00")
        self.assertEqual(portfolio["contribution_margin_percent"], "63.33")
        self.assertEqual(portfolio["operating_profit_margin_percent"], "36.67")
        # Unweighted averages (67.50 and 42.50) would be misleading.

    def test_portfolio_zero_revenue_has_undefined_margin_not_infinity(self):
        data = {
            "currency": "USD",
            "enterprises": [
                {"name": "Idle farm", "units_sold": 0, "unit_price": 100,
                 "variable_cost_per_unit": 10,
                 "allocated_fixed_cost": 800},
            ],
        }
        portfolio = evaluate(data)["portfolio"]
        self.assertEqual(portfolio["operating_profit"], "-800.00")
        self.assertIsNone(portfolio["contribution_margin_percent"])
        self.assertIsNone(portfolio["operating_profit_margin_percent"])

    def test_portfolio_aggregation_without_double_fixed_costs(self):
        data = dict(self.example)
        data["enterprises"] = self.example["enterprises"] + [{
            "name": "Another illustration", "units_sold": 0, "unit_price": 4,
            "variable_cost_per_unit": 2, "allocated_fixed_cost": 100
        }]
        result = evaluate(data)
        self.assertEqual(result["portfolio"]["operating_profit"], "2400.00")
        self.assertEqual(len(result["scenario_results"]), 18)

    def test_resource_intensity_is_computed_from_actual_user_inputs(self):
        crop = dict(self.example["enterprises"][0],
                    land_area_hectares="2.5", irrigation_water_m3="500")
        row = enterprise(crop)
        self.assertEqual(row["units_sold_per_hectare"], "400.0000")
        self.assertEqual(row["operating_profit_per_hectare"], "1000.00")
        self.assertEqual(row["units_sold_per_irrigation_m3"], "2.0000")
        self.assertEqual(row["operating_profit_per_irrigation_m3"], "5.00")
        result = evaluate({"currency": "USD", "enterprises": [crop]})
        self.assertEqual(result["resource_coverage"]["land_area_hectares"]["portfolio_total"], "2.5")
        self.assertEqual(result["resource_coverage"]["irrigation_water_m3"]["portfolio_total"], "500")

    def test_physical_portfolio_totals_preserve_fractional_measured_inputs(self):
        crop = dict(self.example["enterprises"][0],
                    land_area_hectares="0.004", irrigation_water_m3="0.0005")
        result = evaluate({"currency": "USD", "enterprises": [crop]})
        self.assertEqual(result["resource_coverage"]["land_area_hectares"]["portfolio_total"], "0.004")
        self.assertEqual(result["resource_coverage"]["irrigation_water_m3"]["portfolio_total"], "0.0005")
        self.assertEqual(result["version"], "2.0")

    def test_twelve_month_cashflow_exposes_real_liquidity_gap(self):
        sample = json.loads(Path(__file__).with_name("example_inputs.json").read_text(encoding="utf8"))
        report = evaluate(sample)
        cash = report["cashflow"]
        self.assertEqual(len(cash["months"]), 12)
        self.assertEqual([row["closing_cash_balance"] for row in cash["months"][:3]],
                         ["400.00", "-600.00", "100.00"])
        self.assertEqual(cash["minimum_month_end_cash"], "-600.00")
        self.assertEqual(cash["additional_cash_needed_at_month_ends"], "600.00")
        self.assertEqual(cash["first_negative_month"], 2)
        self.assertEqual(cash["ending_cash"], "100.00")
        self.assertEqual(cash["net_operating_cashflow_before_other_uses"], "-100.00")
        self.assertEqual(report["portfolio"]["operating_profit"], evaluate({
            "currency": sample["currency"], "enterprises": sample["enterprises"]})["portfolio"]["operating_profit"])

    def test_cash_debt_proceeds_are_not_fictitious_sales(self):
        data = dict(self.example)
        month = {field: "0.00" for field in (
            "cash_receipts", "operating_payments", "asset_purchases",
            "loan_receipts", "loan_repayments", "other_payments")}
        periods = [dict(month) for _ in range(12)]
        periods[0].update(loan_receipts="1000.00", asset_purchases="900.00", loan_repayments="20.00")
        data["cashflow_plan"] = {"opening_cash":"50.00", "months":periods}
        report = evaluate(data)
        self.assertEqual(report["cashflow"]["ending_cash"], "130.00")
        self.assertEqual(report["cashflow"]["net_operating_cashflow_before_other_uses"], "0.00")
        self.assertEqual(report["portfolio"]["sales_revenue"], "10000.00")

    def test_minimum_month_end_does_not_incorrectly_include_opening_balance(self):
        month = {field: "0.00" for field in (
            "cash_receipts", "operating_payments", "asset_purchases",
            "loan_receipts", "loan_repayments", "other_payments")}
        months = [dict(month) for _ in range(12)]
        months[0]["cash_receipts"] = "60.00"
        report = evaluate(dict(self.example, cashflow_plan={
            "opening_cash": "50.00", "months": months}))
        self.assertEqual(report["cashflow"]["minimum_month_end_cash"], "110.00")
        self.assertEqual(report["cashflow"]["additional_cash_needed_at_month_ends"], "0.00")

    def test_cashflow_rejects_incomplete_unsafe_or_fractional_cent_inputs(self):
        month = {field: "0" for field in (
            "cash_receipts", "operating_payments", "asset_purchases",
            "loan_receipts", "loan_repayments", "other_payments")}
        valid = {"opening_cash":"0", "months":[dict(month) for _ in range(12)]}
        for plan in (
            {**valid,"months":valid["months"][:-1]},
            {**valid,"opening_cash":"-1"},
            {**valid,"opening_cash":"0.001"},
            {**valid,"months":[{**month,"asset_purchases":"0.005"}] + valid["months"][1:]},
            {**valid,"months":[{**month,"loan_receipts":"-1"}] + valid["months"][1:]},
            {**valid,"months":[{**month,"cash_receipts":True}] + valid["months"][1:]},
        ):
            with self.subTest(plan=plan):
                with self.assertRaises(ValueError):
                    evaluate(dict(self.example,cashflow_plan=plan))

    def test_partial_resource_records_do_not_misrepresent_portfolio_totals(self):
        first = dict(self.example["enterprises"][0],
                     name="Irrigated", land_area_hectares="1", irrigation_water_m3=0)
        second = dict(self.example["enterprises"][0], name="Unknown resources")
        data = {"currency": "USD", "enterprises": [first, second]}
        result = evaluate(data)
        water = result["resource_coverage"]["irrigation_water_m3"]
        self.assertEqual(water["provided_enterprises"], 1)
        self.assertFalse(water["complete_for_portfolio"])
        self.assertIsNone(water["portfolio_total"])
        self.assertIsNone(result["results"][0]["operating_profit_per_irrigation_m3"])
        self.assertIsNone(result["results"][1]["operating_profit_per_hectare"])
        self.assertEqual(result["portfolio"]["operating_profit"], "5000.00")

    def test_resource_inputs_reject_zero_area_negative_and_nonfinite_values(self):
        source = self.example["enterprises"][0]
        for field, value in (("land_area_hectares", 0),
                             ("land_area_hectares", -1),
                             ("irrigation_water_m3", -1),
                             ("irrigation_water_m3", "NaN"),
                             ("land_area_hectares", None)):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    enterprise(dict(source, **{field: value}))

    def test_high_unit_currency_resource_ratios_do_not_overflow(self):
        row = {"name": "High-unit case", "units_sold": "1e20",
               "unit_price": "1e20", "variable_cost_per_unit": 1,
               "allocated_fixed_cost": 1, "land_area_hectares": "1e-20",
               "irrigation_water_m3": "1e-20"}
        result = enterprise(row)
        self.assertTrue(result["operating_profit_per_hectare"].endswith(".00"))
        self.assertTrue(result["operating_profit_per_irrigation_m3"].endswith(".00"))

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

    def test_cashflow_csv_contains_twelve_reconciled_months(self):
        import csv
        data = json.loads(Path(__file__).with_name("example_inputs.json").read_text(encoding="utf8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.json"
            output = root / "monthly.csv"
            source.write_text(json.dumps(data), encoding="utf8")
            process = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("calculator.py")),
                 str(source), "--cashflow-csv-output", str(output)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(output.read_text(encoding="utf8").startswith('"month","cash_receipts"'))
            with output.open(encoding="utf8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 12)
            self.assertEqual(rows[1]["closing_cash_balance"], "-600.00")
            self.assertEqual(rows[2]["closing_cash_balance"], "100.00")
            self.assertEqual([row["month"] for row in rows], [str(n) for n in range(1, 13)])

    def test_cashflow_csv_without_required_months_fails_without_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.json"
            output = root / "monthly.csv"
            source.write_text(json.dumps(self.example), encoding="utf8")
            process = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("calculator.py")),
                 str(source), "--cashflow-csv-output", str(output)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(process.returncode, 2)
            self.assertIn("requires a cashflow_plan", process.stderr)
            self.assertFalse(output.exists())


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



if __name__ == "__main__":
    unittest.main()
