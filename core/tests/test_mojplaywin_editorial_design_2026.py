"""Source-only design regression tests for the MojPlayWin main-site refresh.

These tests do not access production, move payments, or modify any subsite.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "core" / "templates" / "mojplaywin"


class MojPlayWinEditorialDesignTests(unittest.TestCase):
    def test_refresh_is_additive_and_scoped_to_mojplaywin_body_classes(self):
        html = (TEMPLATES / "theme.html").read_text(encoding="utf-8")
        self.assertIn("MOJPLAYWIN_EDITORIAL_2026_V1", html)
        self.assertIn("body:is(.mojplaywin-home,.mojplaywin-section,.mojplaywin-store)", html)
        self.assertIn("body.mojplaywin-home .mw-shell>.mw-section:nth-child(2)", html)
        self.assertIn("prefers-reduced-motion:reduce", html)
        self.assertIn("prefers-contrast:more", html)
        self.assertIn('id="mw-all-pages-menu"', html)
        self.assertIn("</style>", html)

    def test_hero_images_are_prioritized_without_changing_image_urls(self):
        cases = {
            "home.html": "site/heroes/game-studio.webp",
            "store.html": "site/heroes/store.webp",
            "section.html": "section_image",
        }
        for name, original_image in cases.items():
            with self.subTest(name=name):
                html = (TEMPLATES / name).read_text(encoding="utf-8")
                self.assertIn(original_image, html)
                self.assertIn('fetchpriority="high" loading="eager" decoding="async"', html)
                self.assertIn('{% include "mojplaywin/theme.html" %}', html)

    def test_existing_store_and_editorial_content_remain_present(self):
        home = (TEMPLATES / "home.html").read_text(encoding="utf-8")
        store = (TEMPLATES / "store.html").read_text(encoding="utf-8")
        self.assertIn("OUR PORTFOLIO · 80%", home)
        self.assertIn("CONNECTED VENTURES · 20%", home)
        self.assertIn("mpw-home-ten-guides", home)
        self.assertIn('href="/store/"', home)
        self.assertIn("{{ product.title }}", store)
        self.assertIn("{{ product.url }}", store)


if __name__ == "__main__":
    unittest.main()
