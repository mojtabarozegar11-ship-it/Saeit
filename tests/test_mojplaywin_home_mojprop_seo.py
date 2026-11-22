"""Source checks for the MojPlayWin homepage MOJ PROP SEO cutover."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "core" / "templates" / "mojplaywin" / "home.html"


class MojPropHomepageSEOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = HOME.read_text(encoding="utf-8")

    def test_homepage_targets_moj_prop(self):
        self.assertIn(
            "{% block title %}MOJ PROP | Simulated Trading Challenge &amp; Risk Management",
            self.source,
        )
        self.assertIn(
            "MOJ PROP by MojPlayWin is a transparent simulated trading challenge",
            self.source,
        )
        self.assertIn(
            "<h1 id=\"mw-home-title\">MOJ PROP: Simulated Trading Challenge &amp; Risk Management</h1>",
            self.source,
        )
        self.assertIn('name="robots" content="index,follow,max-image-preview:large"', self.source)
        self.assertIn('"@type":"WebPage"', self.source)

    def test_homepage_links_all_20_moj_prop_language_editions(self):
        section = self.source.split('id="moj-prop-languages"', 1)[1].split("</section>", 1)[0]
        paths = re.findall(r'href="([^"]+)"', section)
        expected = {
            "/moj-prop/",
            "/moj-prop/languages/zh/",
            "/moj-prop/languages/hi/",
            "/moj-prop/languages/es/",
            "/moj-prop/languages/ar/",
            "/moj-prop/languages/fr/",
            "/moj-prop/languages/bn/",
            "/moj-prop/languages/pt/",
            "/moj-prop/languages/id/",
            "/moj-prop/languages/ur/",
            "/moj-prop/languages/ru/",
            "/moj-prop/languages/de/",
            "/moj-prop/languages/ja/",
            "/moj-prop/languages/ar-eg/",
            "/moj-prop/languages/mr/",
            "/moj-prop/languages/vi/",
            "/moj-prop/languages/te/",
            "/moj-prop/languages/sw/",
            "/moj-prop/languages/tr/",
            "/moj-prop/languages/pcm/",
        }
        self.assertEqual(set(paths), expected)
        self.assertEqual(len(paths), 20)


if __name__ == "__main__":
    unittest.main()
