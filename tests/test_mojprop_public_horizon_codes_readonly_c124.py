"""C124 source and live HTML observer privacy regression; never HTTP POST."""
import io
import json
import unittest
from contextlib import redirect_stdout
from tempfile import TemporaryDirectory
from pathlib import Path

from scripts.mojprop_public_horizon_codes_readonly_c124 import classify, main, EXPECTED

BASE = """<!doctype html><form id="request-form"><select id="horizon">
<option value="urgent">Today</option><option value="week">Week</option>
<option value="month">Month</option><option value="review">Review</option>
</select><input id="consent" type="checkbox"></form>
<script>const endpoint='/moj-prop-intake/';</script>"""


class LiveHorizonContractTests(unittest.TestCase):
    def test_01_valid_four_codes_recognized_without_release(self):
        data = classify(BASE.encode(), {"known": BASE.encode()})
        self.assertTrue(data["frontend_contract_valid"])
        self.assertTrue(data["exact_horizon_choices"])
        self.assertEqual(data["source_class"], "known")
        self.assertFalse(data["commercial_release_authorized"])
        self.assertFalse(data["live_backend_post_or_storage_tested"])

    def test_02_wrong_legacy_choices_fail(self):
        bad = BASE.replace('value="week"', 'value="this-week"')
        data = classify(bad.encode(), {"known": BASE.encode()})
        self.assertFalse(data["exact_horizon_choices"])
        self.assertFalse(data["frontend_contract_valid"])
        self.assertEqual(data["source_class"], "unrecognized_review_required")

    def test_03_missing_consent_fail_closed(self):
        data = classify(BASE.replace('id="consent"', 'id="other"').encode(), {})
        self.assertFalse(data["consent_checkbox_present"])
        self.assertFalse(data["frontend_contract_valid"])

    def test_04_missing_actual_intake_endpoint_fail_closed(self):
        data = classify(BASE.replace("/moj-prop-intake/", "/wrong/").encode(), {})
        self.assertFalse(data["backend_intake_link_present"])
        self.assertFalse(data["frontend_contract_valid"])

    def test_05_no_page_body_is_unknown(self):
        for value in (b"", b"a" * 1_048_577, None):
            data = classify(value, {})
            self.assertFalse(data["body_available"])
            self.assertFalse(data["frontend_contract_valid"])
            self.assertFalse(data["commercial_release_authorized"])

    def test_06_reports_no_body_or_secret_from_file(self):
        private = "customer@example.invalid?csrf=SECRET123"
        with TemporaryDirectory() as root:
            d = Path(root)
            (d / "public").write_text(BASE + "<!--" + private + "-->", encoding="utf-8")
            (d / "source").write_text(BASE, encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["program", str(d / "public"), str(d / "source"), str(d / "source")])
            self.assertEqual(code, 0)
            out = output.getvalue()
            self.assertNotIn(private, out)
            self.assertNotIn("SECRET", out)
            decoded = json.loads(out.split("=", 1)[1])
            self.assertTrue(decoded["frontend_contract_valid"])
            self.assertEqual(decoded["source_class"], "unrecognized_review_required")

    def test_07_actual_main_source_four_choices_match(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("templates/moj-prop/index.html", "templates/moj-prop-v4/index.html"):
            with self.subTest(name=name):
                content = (root / name).read_bytes()
                data = classify(content, {"expected": content})
                self.assertTrue(data["frontend_contract_valid"], name)
                self.assertEqual(data["source_class"], "expected")


if __name__ == "__main__":
    unittest.main()
