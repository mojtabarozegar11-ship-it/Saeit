"""Regression gates for existing Zomorod pages and read-only sitewide audit.

No outbound requests, site writes, login attempts, or payment operations.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/zomorod_public_sitewide_readonly_audit_20261113.py"
SPEC = importlib.util.spec_from_file_location("zomorod_sitewide_readonly", SOURCE)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class ExistingSiteAuditContractTests(unittest.TestCase):
    def parse(self, html):
        page = MOD.Parser()
        page.feed(html)
        page.close()
        return page

    def test_nested_h1_text_is_one_dom_heading(self):
        doc = self.parse("<main><h1>اقتصاد <span>کشاورزی</span> نوین</h1></main>")
        self.assertEqual(len(doc.h1), 1)
        self.assertEqual(MOD.normalize_text(doc.h1[0]), "اقتصاد کشاورزی نوین")

    def test_two_real_h1_elements_remain_two(self):
        doc = self.parse("<main><h1>اول</h1><p>متن</p><h1>دوم</h1></main>")
        self.assertEqual(doc.h1, ["اول", "دوم"])

    def test_empty_h1_is_still_a_heading(self):
        doc = self.parse("<h1></h1><p>متن</p>")
        self.assertEqual(len(doc.h1), 1)

    def test_login_and_first_setup_labels_target_exact_controls(self):
        text = (ROOT / "content/zomorod-business/app.php").read_text(encoding="utf8")
        expected = {
            "zm-login-username": 'name="username" required autocomplete="username"',
            "zm-login-password": 'name="password" type="password" required autocomplete="current-password"',
            "zm-setup-token": 'name="setup_token" type="password" required autocomplete="off"',
            "zm-setup-username": 'name="username" required minlength="5" maxlength="40"',
            "zm-setup-password": 'name="password" type="password" required minlength="14" autocomplete="new-password"',
        }
        for label_id, input_attrs in expected.items():
            with self.subTest(label_id=label_id):
                self.assertEqual(text.count('for="' + label_id + '"'), 1)
                self.assertEqual(text.count('id="' + label_id + '" ' + input_attrs), 1)
        # This test only checks committed PHP source, not a deployed HTML DOM.

    def test_artifact_paths_use_executable_actions_expressions(self):
        text = (ROOT / ".github/workflows/zomorod-sitewide-deep-readonly-20261113.yml").read_text()
        self.assertNotIn(chr(92) + "${{", text)
        self.assertIn("${{ runner.temp }}/zm-sitewide-audit/", text)
        self.assertIn("${{ runner.temp }}/sitewide-public-log.txt", text)
        self.assertIn("${{ runner.temp }}/zm-deep-browser/", text)
        self.assertIn("if-no-files-found: warn", text)

    def test_store_mobile_sha256_wrap_is_localized_and_preserves_original_store(self):
        source = (ROOT / "content/zomorod-v11/store_index.php").read_text(encoding="utf8")
        rule = ".grid article small.muted{overflow-wrap:anywhere;word-break:break-word}"
        self.assertEqual(source.count(rule), 1)
        self.assertIn("SHA-256: ", source)
        self.assertIn("پرداخت آنلاین تا اتصال درگاه غیرفعال است", source)
        self.assertIn("فروشگاه‌های تخصصی زمرد ملل", source)
        self.assertIn("zmStoreDb($private)", source)
        # The rule targets the pre-existing card's unbroken fingerprint only.
        self.assertNotIn("body{overflow-x:hidden}", source)

    def test_store_browser_diagnostic_never_submits_or_writes(self):
        source = (ROOT / "scripts/zomorod_store_overflow_readonly_20261113.cjs").read_text()
        self.assertIn("ZM_STORE_LOCAL_CSS_REHEARSAL", source)
        self.assertIn("localOnly:true", source)
        self.assertIn("https://zomorodmelal.ir/store/", source)
        self.assertNotIn("method:'POST'", source)
        self.assertNotIn("form.submit(", source)


if __name__ == "__main__":
    unittest.main()
