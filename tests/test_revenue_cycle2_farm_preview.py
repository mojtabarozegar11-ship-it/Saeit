"""Economics preview uses existing calculator, real arithmetic, synthetic values."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("farm_preview",
    ROOT / "scripts/revenue_cycle2_farm_preview.py")
f = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f)
EXAMPLE = ROOT / "docs/revenue-p0/example-farm-model.synthetic.json"


class FarmPreviewTests(unittest.TestCase):
    def sample(self):
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_synthetic_result_arithmetic(self):
        r = f.generate(self.sample())
        self.assertEqual(r["portfolio"]["sales_revenue"], "350000000.00")
        self.assertEqual(r["portfolio"]["operating_profit"], "63000000.00")
        self.assertEqual(r["enterprise_results"][0]["break_even_units"], 488)
        self.assertEqual(len(r["scenario_results"]), 9)

    def test_no_real_market_claims(self):
        r = f.generate(self.sample())
        self.assertTrue(r["sample_only"])
        self.assertFalse(r["market_data_independently_verified"])
        self.assertIsNone(r["actual_revenue"])
        self.assertFalse(r["customer_data_used"])

    def test_customer_sample_not_allowed(self):
        obj = self.sample()
        obj["synthetic_example"] = False
        with self.assertRaises(ValueError):
            f.generate(obj)

    def test_sensitive_field_rejected(self):
        obj = self.sample()
        obj["email"] = "private"
        with self.assertRaises(ValueError):
            f.generate(obj)

    def test_nested_credentials_rejected(self):
        obj = self.sample()
        obj["enterprises"][0]["private_key"] = "hidden"
        with self.assertRaises(ValueError):
            f.generate(obj)

    def test_invalid_currency_blocked(self):
        obj = self.sample()
        obj["currency"] = "NOT REAL $$$"
        with self.assertRaises(ValueError):
            f.generate(obj)

    def test_bad_economics_blocked(self):
        obj = self.sample()
        obj["enterprises"][0]["unit_price"] = "NaN"
        with self.assertRaises(ValueError):
            f.generate(obj)

    def test_cli_real_subprocess_success(self):
        proc = subprocess.run([sys.executable,
            str(ROOT / "scripts/revenue_cycle2_farm_preview.py"),
            str(EXAMPLE)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["portfolio"]["operating_profit"],
                         "63000000.00")


if __name__ == "__main__":
    unittest.main()
