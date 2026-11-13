"""Isolated evidence tests for the public GET-only store CSS parity observer."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/zomorod_store_public_css_parity_readonly_20261114.py"
spec = importlib.util.spec_from_file_location("zm_store_css_parity", FILE)
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)


class PublicCssParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MOD.PHP_SOURCE.read_text(encoding="utf8")
        cls.assert_source = cls.source  # direct source, not live PHP

    def page(self, css=""):
        return "<!doctype html><html><head><style>" + css + "</style></head><body><h1>فروشگاه زمرد ملل</h1></body></html>"

    def test_exact_public_css_matches_both_markers(self):
        result = MOD.compare(self.source, self.page(MOD.CSS_RULE + MOD.GRID_RULE))
        self.assertTrue(result["public_parity_for_two_css_markers"])
        self.assertFalse(result["cpanel_active_file_hash_verified"])

    def test_missing_live_css_does_not_claim_source_parity(self):
        result = MOD.compare(self.source, self.page(".grid article small.muted{white-space:normal}"))
        self.assertFalse(result["public_parity_for_two_css_markers"])
        self.assertFalse(result["public_css_rule_present"])

    def test_markers_outside_style_are_not_validated_as_styles(self):
        html = "<!doctype html><p>" + MOD.CSS_RULE + MOD.GRID_RULE + "</p>"
        result = MOD.compare(self.source, html)
        self.assertFalse(result["public_parity_for_two_css_markers"])

    def test_partial_css_only_is_not_full_parity(self):
        result = MOD.compare(self.source, self.page(MOD.CSS_RULE))
        self.assertTrue(result["public_css_rule_present"])
        self.assertFalse(result["public_grid_rule_present"])
        self.assertFalse(result["public_parity_for_two_css_markers"])

    def test_unexpected_host_non_200_and_content_type_are_rejected(self):
        cases = [
            {"final_url": "https://external.invalid/store/"},
            {"status": 500},
            {"content_type": "application/json"},
        ]
        for kw in cases:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                MOD.compare(self.source, self.page(MOD.CSS_RULE + MOD.GRID_RULE), **kw)

    def test_report_never_claims_real_browser_or_server_identity(self):
        result = MOD.compare(self.source, self.page(MOD.CSS_RULE + MOD.GRID_RULE))
        self.assertFalse(result["browser_overflow_verified_by_this_check"])
        self.assertFalse(result["cpanel_active_file_hash_verified"])
        self.assertEqual((result["site_writes"], result["forms_submitted"], result["payments"]), (0, 0, 0))
        self.assertTrue(result["release_gate"].startswith("blocked_"))

    def test_source_is_get_only_and_does_not_require_ssh_secrets(self):
        content = FILE.read_text(encoding="utf8")
        self.assertIn('method="GET"', content)
        self.assertIn('SameHostRedirect', content)
        for forbidden in ("subprocess", "ssh ", "POST(", "VPS_SSH_PRIVATE_KEY", "SAEIT_HOST_SSH_PRIVATE_KEY"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
