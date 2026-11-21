"""Read-only invariants for MOJ PROP global-locale, no-PII click counters."""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts"/"mojprop_global_funnel_tracking_20261121.py"
spec=importlib.util.spec_from_file_location("mpw_locale_cta_metrics",SRC)
metrics=importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)

class LocaleClickAttributionTests(unittest.TestCase):
    def test_20_locales_only(self):
        self.assertEqual(len(metrics.CODES),20)
        self.assertEqual(len(set(metrics.CODES)),20)
        self.assertIn("pcm",metrics.CODES)
        self.assertIn("ar-eg",metrics.CODES)
        self.assertIn("en",metrics.CODES)
    def test_only_opt_in_visible_user_clicks(self):
        js=metrics.JS
        self.assertIn("document.addEventListener(\"click\"",js)
        self.assertIn("if(!ev.isTrusted)return",js)
        self.assertIn('data-mpw-locale-event',js)
        self.assertIn('type!=="program"&&type!=="starter30"',js)
        self.assertIn("navigator.sendBeacon",js)
        self.assertIn('credentials:"omit"',js)
        self.assertNotRegex(js, r"\blocalStorage\s*(?:\.|\[)")
        self.assertNotIn("document.cookie",js)
        self.assertNotIn("utm_source",js)
        self.assertNotIn("analytics.google",js)
    def test_validated_same_origin_post(self):
        php=metrics.PHP
        self.assertIn("HTTP_ORIGIN",php)
        self.assertIn("HTTP_SEC_FETCH_SITE",php)
        self.assertIn("HTTP_REFERER",php)
        self.assertIn("application/x-www-form-urlencoded",php)
        self.assertIn("http_response_code(405)",php)
        self.assertIn("http_response_code(403)",php)
        self.assertIn("http_response_code(400)",php)
        self.assertIn("X-Robots-Tag: noindex, nofollow",php)
        self.assertIn("flock($handle, LOCK_EX)",php)
        self.assertIn("gmdate('Ymd')",php)
        self.assertIn("http_response_code(204)",php)
    def test_minimum_private_counters_no_identifiers(self):
        php=metrics.PHP
        self.assertIn("click_events_not_unique_visitors",php)
        for forbidden in ("REMOTE_ADDR","HTTP_USER_AGENT","HTTP_COOKIE",
                          "wallet_address","email_address","HTTP_AUTHORIZATION",
                          "credit_card","$_COOKIE","$_SESSION","setcookie("):
            self.assertNotIn(forbidden,php)
        self.assertIn("'c+'",php)
        self.assertIn("umask(0077)",php)
        self.assertIn("100000",php)
        self.assertIn("action === 'probe'",php)
        self.assertIn("not_unique_visitors",metrics.REPORT_CONTENT)
    def test_fail_closed_no_overwrite_and_page_content(self):
        source=SRC.read_text()
        self.assertIn("LOCALIZED_PAGE_DRIFT",source)
        self.assertIn("ROOT_ROBOTS_DRIFT",source)
        self.assertIn("refuse to overwrite",source)
        self.assertIn("Concurrent page edit",source)
        self.assertIn("Backup integrity error",source)
        self.assertIn("if sha(p.read_bytes())!=sha(data)",source)
        self.assertIn('Disallow: /moj-prop/metrics/',source)
        self.assertIn("id=\"mojprop-global-cta-events-20261121\"",source)
    def test_precise_replacement(self):
        x="good-needle-and-no-changes"
        self.assertEqual(metrics.exactly(x,"needle","updated"),"good-updated-and-no-changes")
        with self.assertRaises(RuntimeError):
            metrics.exactly(x,"missing","bad")
        with self.assertRaises(RuntimeError):
            metrics.exactly("duplicate duplicate","duplicate","bad")

if __name__=="__main__":
    unittest.main()
