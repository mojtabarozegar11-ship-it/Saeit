"""F28 Greenhouse Margin Lab: bounded deterministic pilot acceptance tests.

Run: python -m unittest -v tests.test_greenhouse_margin_lab_pilot
No commercial or on-site acceptance is claimed by these tests.
"""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "product_recipes/greenhouse_crop_margin/greenhouse_margin_lab_pilot.html"


class GreenhouseLabPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")

    def test_standalone_no_remote_deps(self):
        x = self.html.lower()
        self.assertIn("<!doctype html>", x)
        self.assertIn('name="viewport"', x)
        self.assertNotIn("<script src=", x)
        self.assertNotIn("<iframe", x)
        self.assertNotIn("fetch(", x)
        self.assertNotIn("xmlhttprequest", x)
        self.assertNotIn("https://", x)
        self.assertNotIn("http://", x)

    def test_input_and_readability_contract(self):
        for field in ("area", "yield", "price", "variable", "fixed", "reject", "currency"):
            self.assertIn('id="' + field + '"', self.html)
        self.assertIn('role="alert"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn("Nine scenario stress tests", self.html)
        self.assertIn("Export results CSV", self.html)

    def test_sales_and_model_limits_explicit(self):
        for text in (
            "No commercial license or live sales is activated",
            "Specialist review, itemized rights, owner approval",
            "excludes tax, depreciation, finance",
            "No network, trackers, payments or data collection",
        ):
            self.assertIn(text, self.html)

    def test_deterministic_arithmetic_and_invalid_inputs(self):
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable; computation test must run in Node-enabled QA")
        match = re.search(r"const calculate=(function calculate\(v\)\{.*?\});\s*const keys=", self.html, re.S)
        self.assertIsNotNone(match, "pure calculator function must be extractable")
        code = (
            "const calculate=" + match.group(1) + ";\n"
            "const a={area:100,yield:10,price:3,variable:5,fixed:500,reject:10,currency:'USD'};\n"
            "const r=calculate(a);"
            "if(r.gross!==1000||r.saleable!==900||r.revenue!==2700||r.total!==1000||r.margin!==1700||Math.abs(r.breakEven-(1000/900))>1e-9)throw Error('fixture');\n"
            "for(const b of [{...a,reject:100},{...a,yield:0}]){if(calculate(b).breakEven!==null)throw Error('zero-saleable');}\n"
            "for(const b of [{...a,area:0},{...a,price:-1},{...a,reject:101},{...a,yield:'oops'},{...a,area:'Infinity'}]){let rejected=false;try{calculate(b)}catch(_){rejected=true}if(!rejected)throw Error('validation');}\n"
            "console.log('F28_OFFLINE_CALC_ACCEPTANCE=PASS');"
        )
        result = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr[-1200:])
        self.assertIn("F28_OFFLINE_CALC_ACCEPTANCE=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
