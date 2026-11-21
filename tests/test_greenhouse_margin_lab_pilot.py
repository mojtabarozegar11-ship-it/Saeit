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


    def test_model_parity_with_existing_python_engine(self):
        """Twenty deterministic scenarios must match the independent recipe engine."""
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        import importlib.util
        import json
        import math
        import random

        path = ROOT / "product_recipes/greenhouse_crop_margin/calculator.py"
        spec = importlib.util.spec_from_file_location("f28_reference_engine", path)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        rng = random.Random(28002026)
        samples = [
            {"area": 100, "yield": 10, "price": 3, "variable": 5,
             "fixed": 500, "reject": 10, "currency": "USD"},
            {"area": 1, "yield": 0, "price": 3, "variable": 0,
             "fixed": 10, "reject": 0, "currency": "EUR"},
            {"area": 100, "yield": 5, "price": 0, "variable": 0,
             "fixed": 0, "reject": 100, "currency": "CAD"},
        ]
        for _ in range(17):
            samples.append({
                "area": rng.randint(1, 10000) / 10,
                "yield": rng.randint(0, 400) / 10,
                "price": rng.randint(0, 5000) / 100,
                "variable": rng.randint(0, 10000) / 100,
                "fixed": rng.randint(0, 200000),
                "reject": rng.randint(0, 100),
                "currency": "USD"
            })
        match = re.search(
            r"const calculate=(function calculate\(v\)\{.*?\});\s*const keys=",
            self.html, re.S
        )
        self.assertIsNotNone(match)
        js = ("const calculate=" + match.group(1) + ";\n"
              "const samples=" + json.dumps(samples) + ";\n"
              "process.stdout.write(JSON.stringify(samples.map(calculate)));\n")
        proc = subprocess.run(["node", "-e", js], capture_output=True,
                              text=True, timeout=15, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr[-1000:])
        actual = json.loads(proc.stdout)
        self.assertEqual(len(actual), len(samples))
        fields = {
            "gross": "gross_yield_kg",
            "saleable": "saleable_yield_kg",
            "revenue": "sales_revenue",
            "total": "total_cost",
            "margin": "net_margin",
            "marginPerArea": "net_margin_per_m2",
            "breakEven": "break_even_price_per_kg"
        }
        for scenario, produced in zip(samples, actual):
            ref = engine.calculate({
                "area_m2": scenario["area"],
                "expected_yield_kg_per_m2": scenario["yield"],
                "price_per_kg": scenario["price"],
                "variable_cost_per_m2": scenario["variable"],
                "fixed_cost_total": scenario["fixed"],
                "rejection_rate_percent": scenario["reject"],
                "currency": scenario["currency"],
            })
            self.assertEqual(produced["currency"], scenario["currency"])
            for browser_key, engine_key in fields.items():
                wanted = ref["results"][engine_key]
                observed = produced[browser_key]
                if wanted is None:
                    self.assertIsNone(observed, (scenario, browser_key))
                else:
                    self.assertTrue(math.isclose(
                        observed, float(wanted), rel_tol=1e-9,
                        abs_tol=0.011
                    ), (scenario, browser_key, wanted, observed))

    def test_real_headless_browser_renders_numbers_and_nine_rows(self):
        """Execute HTML in a headless desktop browser rather than just checking text."""
        import os
        import tempfile

        chrome = next((shutil.which(name) for name in
                       ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable")
                       if shutil.which(name)), None)
        if not chrome:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                self.fail("CI missing headless Chrome: F28 browser QA was not executed")
            self.skipTest("Browser not installed in local environment")
        with tempfile.TemporaryDirectory(prefix="f28-browser-") as tmp:
            cmd = [
                chrome, "--headless", "--no-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-background-networking", "--no-first-run",
                "--disable-extensions", "--disable-default-apps",
                "--no-proxy-server", "--virtual-time-budget=2000",
                "--user-data-dir=" + tmp, "--dump-dom", HTML.resolve().as_uri()
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=35, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr[-1000:])
            dom = proc.stdout
            self.assertIn("1,700.00 USD", dom, "Margin not calculated in browser")
            self.assertIn("2,700.00 USD", dom, "Revenue not calculated in browser")
            self.assertIn("900.00 kg", dom, "Saleable mass not calculated in browser")
            self.assertIn("id=\"rows\"", dom)
            rendered_rows = re.search(r'<tbody id="rows">(.*?)</tbody>', dom, re.S)
            self.assertIsNotNone(rendered_rows, "Missing rendered matrix")
            self.assertEqual(rendered_rows.group(1).count("<tr>"), 9)
            self.assertNotIn('id="export" type="button" class="secondary" disabled', dom)


if __name__ == "__main__":
    unittest.main()
