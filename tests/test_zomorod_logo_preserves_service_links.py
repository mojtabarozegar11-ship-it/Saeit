"""Regression guard: branding must never overwrite newer customer-facing HTML."""
import importlib.util
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/deploy_zomorod_transparent_logo.py"
SERVICES = ROOT / "content/zomorod-nova-pages/services.html"

spec = importlib.util.spec_from_file_location("zomorod_logo_only", SCRIPT)
logo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logo)


class _ServiceLinkReader(HTMLParser):
    """Collect accessible labels and hrefs independently of presentational markup."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._anchor = (dict(attrs).get("href"), [])

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            href, parts = self._anchor
            self.links.append(("".join(parts).strip(), href))
            self._anchor = None


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

    def test_canonical_service_source_preserves_each_specialist_intent(self):
        parser = _ServiceLinkReader()
        parser.feed(SERVICES.read_text(encoding="utf-8"))
        expected = {
            "استعلام ارزیابی اقتصادی ←": "economics",
            "استعلام مدیریت منابع ←": "water",
            "استعلام امکان‌سنجی ←": "feasibility",
            "درخواست تحلیل اقتصادی تخصصی مزرعه": "economics",
        }
        for label, topic in expected.items():
            with self.subTest(label=label):
                hrefs = [href for text, href in parser.links if text == label]
                self.assertEqual(hrefs, ["/ask-master/index.php?service=1&topic=" + topic])


    def test_service_page_has_one_semantic_shell(self):
        html = SERVICES.read_text(encoding="utf-8")
        self.assertEqual(html.count("<header"), 1)
        self.assertEqual(html.count("<footer"), 1)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('class="zm-v7-header"', html)
        self.assertIn('class="zm-v7-footer"', html)
        self.assertNotIn('class="zm-site-header"', html)
        self.assertNotIn('class="zm-footer"', html)


if __name__ == "__main__":
    unittest.main()
