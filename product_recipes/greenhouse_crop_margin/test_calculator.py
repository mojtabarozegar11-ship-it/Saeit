"""Functional tests for the greenhouse crop margin planning tool."""
import json
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
        self.assertEqual(values["break_even_price_per_kg"], "1.85")

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
