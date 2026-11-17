"""Dependency-free AGR-01 report generation checks: private HTML, no network."""
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
from unittest import TestCase

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/agr01_generate_client_report.py"


def load_script():
    name = "agr01_report_cli_tested"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FarmReportDeliverableTests(TestCase):
    def setUp(self):
        self.cli = load_script()
        self.inputs = {
            "area_hectares": "2", "production_tonnes_per_hectare": "5",
            "farmgate_price_per_tonne": "100", "variable_cost_per_hectare": "200",
            "fixed_cost_total": "100", "irrigation_m3_per_hectare": "2000",
            "currency_code": "USD",
        }

    def test_report_from_client_numbers_produces_real_economic_figures(self):
        x = self.cli.report_for_input(self.inputs)
        self.assertEqual(x["gross_revenue"], "1000.00")
        self.assertEqual(x["operating_surplus"], "500.00")
        self.assertFalse(x["buyer_payment_collected"])

    def test_html_is_printable_persian_and_safely_escaped(self):
        report = self.cli.report_for_input(self.inputs)
        report["currency_code"] = "<script>alert('x')</script>"
        html = self.cli.render_printable_html(report)
        self.assertIn("dir='rtl'", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("گزارش اقتصادی AGR-01", html)

    def test_command_creates_private_new_html_report_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "farm.json", root / "report.html"
            source.write_text(json.dumps(self.inputs), encoding="utf8")
            self.assertEqual(self.cli.main([
                "--input", str(source), "--output", str(output)
            ]), 0)
            self.assertIn("500.00", output.read_text(encoding="utf8"))
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            with self.assertRaises(ValueError):
                self.cli.main(["--input", str(source), "--output", str(output)])

    def test_extra_client_identity_fields_are_not_included_in_private_report(self):
        with self.assertRaises(ValueError):
            self.cli.report_for_input({**self.inputs, "buyer_email": "buyer@farmco.org"})

    def test_missing_required_inputs_and_unbounded_file_refused(self):
        with self.assertRaises(ValueError):
            self.cli.report_for_input({"currency_code": "USD"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "too_big.json"
            source.write_text("a" * 11000, encoding="ascii")
            with self.assertRaises(ValueError):
                self.cli.main(["--input", str(source), "--output", str(root / "result.html")])

    def test_invalid_product_input_does_not_create_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inp, out = root / "farm.json", root / "report.html"
            inp.write_text(json.dumps({**self.inputs, "farmgate_price_per_tonne": "NaN"}))
            with self.assertRaises(ValueError):
                self.cli.main(["--input", str(inp), "--output", str(out)])
            self.assertFalse(out.exists())

    def test_unknown_report_shape_rejected_before_document_generation(self):
        with self.assertRaises(ValueError):
            self.cli.render_printable_html({"gross_revenue": "999"})
