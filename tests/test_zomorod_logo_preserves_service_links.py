"""Regression guard: branding must never overwrite newer customer-facing HTML."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/deploy_zomorod_transparent_logo.py"
SERVICES = ROOT / "content/zomorod-nova-pages/services.html"

spec = importlib.util.spec_from_file_location("zomorod_logo_only", SCRIPT)
logo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logo)


class LogoOnlyRegression(unittest.TestCase):
    def test_existing_new_logo_preserves_every_byte(self):
        html = b"<a href='/ask-master/index.php?service=1&amp;topic=economics'>Ask</a>" + logo.NEW_PATH
        self.assertEqual(logo.logo_only(html), html)

    def test_legacy_logo_only_preserves_contextual_links(self):
        html = (b"<a href='/ask-master/index.php?service=1&amp;topic=water'>Water</a>"
                + logo.OLD_PATH + b"<aside>Current seasonal offer</aside>")
        transformed = logo.logo_only(html)
        self.assertEqual(transformed, html.replace(logo.OLD_PATH, logo.NEW_PATH))
        self.assertIn(b"topic=water", transformed)
        self.assertIn(b"Current seasonal offer", transformed)

    def test_unknown_branding_refused(self):
        with self.assertRaisesRegex(RuntimeError, "no known company logo"):
            logo.logo_only(b"<p>no approved logo reference</p>")

    def test_canonical_service_source_has_three_distinct_topics(self):
        html = SERVICES.read_text(encoding="utf-8")
        for topic in ("economics", "water", "feasibility"):
            with self.subTest(topic=topic):
                self.assertEqual(html.count("?service=1&amp;topic=" + topic), 1)


if __name__ == "__main__":
    unittest.main()
