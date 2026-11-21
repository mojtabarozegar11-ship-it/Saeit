"""Static safety properties of the first-party collector and installer."""
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parents[1]
PHP = BASE / "deploy/mpw_measure/collect.php"
JS = BASE / "deploy/mpw_measure/tracker.js"
INSTALL = BASE / "deploy/mpw_measure/install.py"


class MeasurementAssetTests(unittest.TestCase):
    def test_website_has_no_third_party_analytics_dependencies(self):
        js = JS.read_text(encoding="utf-8")
        for banned in ("gtag(", "google-analytics.com", "matomo", "pixel.facebook",
                       "api.segment.io", "sendBeacon", "credentials: \"include\""):
            self.assertNotIn(banned, js)
        self.assertIn("mpw_measure_consent_v1", js)
        self.assertIn('credentials: "omit"', js)

    def test_collector_does_not_persist_form_fields_or_ip(self):
        php = PHP.read_text(encoding="utf-8")
        for bad in ("$_POST", "HTTP_X_FORWARDED_FOR", "$_SERVER['REMOTE_ADDR']",
                    "wallet_address", "invoice_ref", "order_id"):
            self.assertNotIn(bad, php)
        self.assertIn("JSON_UNESCAPED_SLASHES", php)
        self.assertIn("flock($fh, LOCK_EX)", php)

    def test_no_factory_db_or_wsgi_operations_in_installer(self):
        content = INSTALL.read_text(encoding="utf-8")
        for bad in ("manage.py", "passenger_wsgi.py", "config/settings.py",
                    "core/models.py", "touch tmp/restart.txt", "migrate"):
            self.assertNotIn(bad, content)
        self.assertIn("store/index.html", content)
        self.assertIn("moj-prop/starter-30-trx/index.html", content)


if __name__ == "__main__":
    unittest.main()
