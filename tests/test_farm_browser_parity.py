"""Cross-runtime quality gates for the offline browser edition.

The base Python-only manufacturer still works without Node; if Node is installed,
the full JS arithmetic comparison runs against the independent Python engine.
"""
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'product_recipes' / 'farm_enterprise_economics'
sys.path.insert(0, str(ROOT))
from calculator import evaluate


def browser_calculate(input_data):
    code = (
        "const fs=require('fs');"
        "const model=require('./offline_engine.js');"
        "const data=JSON.parse(fs.readFileSync(0,'utf8'));"
        "try{process.stdout.write(JSON.stringify({ok:true,value:model.evaluate(data)}));}"
        "catch(error){process.stdout.write(JSON.stringify({ok:false,error:error.message}));}"
    )
    result = subprocess.run(
        [shutil.which("node"), "-e", code], input=json.dumps(input_data),
        text=True, capture_output=True, cwd=ROOT, timeout=15, check=True,
    )
    return json.loads(result.stdout)


def crop(name, quantity, price, variable, fixed, fee="0", **additional):
    return {
        "name": name, "units_sold": str(quantity), "unit_price": str(price),
        "variable_cost_per_unit": str(variable), "allocated_fixed_cost": str(fixed),
        "selling_fee_percent": str(fee), **additional,
    }


class OfflineBrowserContractTests(unittest.TestCase):
    def test_browser_files_are_packaged_as_maker_source(self):
        # Recipes are copied alone to isolated customers / QA sandboxes.
        # Their tests MUST NOT depend on the manufacturer script being beside
        # the copied folder. Verify the full contract in either layout.
        expected = ("offline_calculator.html", "offline_engine.js",
                    "offline_ui.js", "test_offline_package.py")
        for name in expected:
            self.assertTrue((ROOT / name).is_file(), name)
            self.assertFalse((ROOT / name).is_symlink(), name)
        self.assertTrue((ROOT / "README.md").is_file())
        self.assertTrue((ROOT / "test_calculator.py").is_file())
        maker_path = ROOT.parent.parent / "scripts" / "factory_product_maker.py"
        if maker_path.is_file():
            from importlib.util import module_from_spec, spec_from_file_location
            spec = spec_from_file_location("browser_recipe_maker", maker_path)
            maker = module_from_spec(spec)
            spec.loader.exec_module(maker)
            _, files = maker.inspect_recipe(ROOT)
            for name in expected:
                self.assertIn(name, files)

    def test_interface_has_offline_content_policy_and_no_remote_assets(self):
        body = (ROOT / "offline_calculator.html").read_text(encoding="utf-8")
        controller = (ROOT / "offline_ui.js").read_text(encoding="utf-8")
        engine = (ROOT / "offline_engine.js").read_text(encoding="utf-8")
        self.assertIn("default-src 'none'", body)
        self.assertIn('name="viewport"', body)
        self.assertIn('aria-live="assertive"', body)
        self.assertIn('offline_engine.js', body)
        self.assertIn('offline_ui.js', body)
        self.assertNotIn("http://", body)
        self.assertNotIn("https://", body)
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "localStorage", "eval("):
            self.assertNotIn(forbidden, controller)
            self.assertNotIn(forbidden, engine)


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable: browser parity separately verified in CI")
class OfflineBrowserArithmeticParityTests(unittest.TestCase):
    def assert_parity(self, data):
        python = evaluate(data)
        browser = browser_calculate(data)
        self.assertTrue(browser["ok"], browser.get("error"))
        actual = browser["value"]
        self.assertEqual(actual["currency"], python["currency"])
        self.assertEqual(actual["portfolio"], python["portfolio"])
        self.assertEqual(actual["resource_coverage"], python["resource_coverage"])
        self.assertEqual(actual["scenario_results"], python["scenario_results"])
        for browser_row, python_row in zip(actual["results"], python["results"]):
            for key, expected in python_row.items():
                got = browser_row[key]
                if key in ("units_sold", "selling_fee_percent", "land_area_hectares",
                           "irrigation_water_m3", "margin_of_safety_units") and expected is not None:
                    from decimal import Decimal
                    self.assertEqual(Decimal(str(got)), Decimal(str(expected)), key)
                else:
                    self.assertEqual(got, expected, key)

    def test_illustrative_two_enterprise_example(self):
        self.assert_parity(json.loads((ROOT / "example_inputs.json").read_text()))

    def test_zero_fees_zero_water_and_nonpositive_contribution(self):
        self.assert_parity({"currency": "IRR", "enterprises": [
            crop("Rainfed", 0, 14, 4, 550, irrigation_water_m3="0", land_area_hectares="0.25"),
            crop("Loss", 18, 7, 8, 100, 100),
            crop("Zero cost", 10, 0, 0, 0),
        ]})

    def test_rounding_ties_high_currency_and_partial_resources(self):
        self.assert_parity({"currency": "IRR", "enterprises": [
            crop("Large", "999999999999.125", "1000000000.005", "35.555",
                 "987654321.125", "2.75", land_area_hectares="0.005"),
            crop("Small", "2.25", "0.01", "0.005", "0.005", "0"),
        ]})

    def test_break_even_ceiling_and_sensitivity_fractions(self):
        self.assert_parity({"currency": "USD", "enterprises": [
            crop("High precision", "0.00003", "0.30005", "0.20001", "0.00001", "0.001",
                 land_area_hectares="0.01", irrigation_water_m3="0.0005"),
            crop("Zero margin", 100, 10, 10, 50, 0),
        ]})

    def test_tiny_physical_totals_never_round_to_zero_currency_cents(self):
        self.assert_parity({"currency": "USD", "enterprises": [
            crop("Micro plot", "1", "100", "40", "10", "0",
                 land_area_hectares="0.004", irrigation_water_m3="0.0005")
        ]})

    def test_deterministic_differential_cases(self):
        # Independent evaluation of 30 varied multi-enterprise farm scenarios.
        rng = random.Random(20261106)
        for case in range(30):
            rows = []
            for row in range(1 + case % 5):
                entry = crop(
                    'Activity ' + str(row + 1),
                    str(rng.randrange(0, 400000)) + '.' + str(rng.randrange(1000)).zfill(3),
                    str(rng.randrange(0, 100000)) + '.' + str(rng.randrange(1000)).zfill(3),
                    str(rng.randrange(0, 20000)) + '.' + str(rng.randrange(1000)).zfill(3),
                    str(rng.randrange(0, 900000)) + '.' + str(rng.randrange(1000)).zfill(3),
                    str(rng.randrange(0, 100)) + '.' + str(rng.randrange(1000)).zfill(3)
                    if rng.randrange(3) else '100',
                )
                if rng.randrange(2):
                    entry['land_area_hectares'] = str(rng.randrange(1, 10000) / 100)
                if rng.randrange(2):
                    entry['irrigation_water_m3'] = str(rng.randrange(0, 50000))
                rows.append(entry)
            with self.subTest(scenario=case):
                self.assert_parity({'currency': 'CAD', 'enterprises': rows})

    def test_reject_formula_label_and_unbounded_input(self):
        for name in ("=SUM(A1:A2)", "+cmd", "@DDE", "Normal\n=FORMULA"):
            invalid = {"currency": "USD", "enterprises": [crop(name, 2, 10, 3, 0)]}
            self.assertFalse(browser_calculate(invalid)["ok"])
            with self.assertRaises(ValueError):
                evaluate(invalid)
        invalid = {"currency": "USD", "enterprises": [crop("Valid", 2, "Infinity", 3, 0)]}
        self.assertFalse(browser_calculate(invalid)["ok"])

    def test_unquoted_json_decimals_and_unsafe_integers_fail_closed(self):
        for value in (0.1, 9007199254740992):
            invalid = {"currency": "USD", "enterprises": [{
                **crop("Example", 10, "1", "1", "1"), "unit_price": value
            }]}
            self.assertFalse(browser_calculate(invalid)["ok"])


if __name__ == "__main__":
    unittest.main()
