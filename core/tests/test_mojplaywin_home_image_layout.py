"""Guarantee 17 unique existing image sources and one home layout on MojPlayWin MAIN only."""
from pathlib import Path
import re

from django.test import SimpleTestCase

from core.mojplaywin_views import FEATURES


ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "core/templates/mojplaywin/home.html"
MAIN_THEME = ROOT / "core/templates/mojplaywin/theme.html"
PARENT = ROOT / "core/templates/base.html"
LEGACY = ROOT / "core/templates/brands/mojplaywin/base.html"
PUBLIC_IMAGES = ROOT / "core/static"


class MojPlayWinMainHomeImageAndLayoutTests(SimpleTestCase):
    def test_editorial_hero_and_ten_illustrations_are_all_unique(self):
        html = HOME.read_text(encoding="utf-8")
        paths = re.findall(r"{% static '([^']+)' %}", html)
        self.assertEqual(len(paths), 11, "The home hero and ten original guide illustrations must remain")
        self.assertEqual(len(set(paths)), 11, "Never show the same image twice in the main home")
        for path in paths:
            self.assertTrue((PUBLIC_IMAGES / path).is_file(), path)

    def test_six_feature_images_do_not_repeat_home_editorial_illustrations(self):
        html = HOME.read_text(encoding="utf-8")
        fixed = set(re.findall(r"{% static '([^']+)' %}", html))
        categories = [item["image"] for item in FEATURES]
        self.assertEqual(len(categories), 6)
        self.assertEqual(len(set(categories)), 6)
        self.assertFalse(fixed.intersection(categories), "All 17 main home images must be distinct")
        for path in categories:
            self.assertTrue((PUBLIC_IMAGES / path).is_file(), path)
        self.assertEqual(len(fixed | set(categories)), 17)

    def test_all_original_home_articles_and_site_directory_are_preserved(self):
        html = HOME.read_text(encoding="utf-8")
        self.assertEqual(html.count('id="home-guide-'), 10)
        self.assertIn('id="site-directory"', html)
        self.assertIn('id="mpw-home-ten-guides"', html)
        self.assertIn('OUR PORTFOLIO', html)
        self.assertIn('CONNECTED VENTURES', html)
        self.assertIn('href="/store/"', html)
        self.assertIn('href="/games/"', html)
        self.assertIn('href="/research/"', html)
        self.assertIn('{% for item in features %}', html)
        self.assertIn('{% for item in ventures %}', html)

    def test_full_home_uses_one_shared_width_wrapper(self):
        html = HOME.read_text(encoding="utf-8")
        self.assertEqual(html.count('<div class="mw-shell">'), 1)
        self.assertNotIn('</div>\n{% comment %}Additive ten illustrated editorial', html)
        self.assertIn('</div>\n{% include "mojplaywin/footer.html" %}', html)

    def test_scope_does_not_touch_shared_or_legacy_templates(self):
        home = HOME.read_text(encoding="utf-8")
        self.assertIn('{% include "mojplaywin/theme.html" %}', home)
        self.assertIn('{% include "mojplaywin/footer.html" %}', home)
        self.assertNotIn("mojplaywin/unified_visual_tokens.html", LEGACY.read_text(encoding="utf-8"))
        self.assertNotIn("mojplaywin/unified_visual_tokens.html", PARENT.read_text(encoding="utf-8"))
        self.assertEqual(MAIN_THEME.read_text(encoding="utf-8").count('{% include "mojplaywin/unified_visual_tokens.html" %}'), 1)
