"""Regression guard: uniform dark-olive full-width backgrounds on EXISTING inner pages.

This is a constrained color-only change; never modify / homepage or create templates.
No network access, payment, deployment or writes.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
OLIVE = "#252b19"


class ExistingInteriorOliveBackground(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tala = (ROOT / "public/tala/index.html").read_text(encoding="utf8")
        cls.academy = (ROOT / "public/amozeshgah/index.html").read_text(encoding="utf8")

    def test_tala_has_one_dark_olive_base_and_no_black_full_width_bands(self):
        s = self.tala
        self.assertIn('meta name="theme-color" content="#252b19"', s)
        self.assertIn(':root{--bg:#252b19;', s)
        for marker in (
            'body{margin:0;background:var(--bg);',
            '.header{position:sticky;top:0;z-index:20;background:var(--bg);',
            '.tala-live-market{background:var(--bg);',
            '.ticker{padding:16px 0;border-block:1px solid var(--line);background:var(--bg)}',
            '.tools{background:var(--bg);border-block:1px solid var(--line)}',
            '.footer{margin-top:80px;padding:46px 0 24px;background:var(--bg);',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, s)
        for old in ('background:#11120fe8', 'background:#161712',
                    'background:#0d0e0c',
                    'background:linear-gradient(180deg,#151611,#11120f)'):
            with self.subTest(old=old):
                self.assertNotIn(old, s)

    def test_tala_preserves_active_components_and_no_layout_replacement(self):
        s = self.tala
        for key in ('id="live-market"', 'id="market"', 'id="calculators"',
                    'id="showcase"', 'id="studio"', 'id="learn"',
                    'id="contact"', '<nav class="links"', 'class="footer"',
                    'href="/tala/admin/"', 'aria-label="جستجو"'):
            self.assertIn(key, s)
        self.assertIn('color:var(--gold)', s)
        self.assertIn('font-family:Vazirmatn', s)

    def test_academy_gold_borders_unchanged_but_all_full_width_strips_olive(self):
        s = self.academy
        self.assertIn('body.academy-page{background:#252b19;color:#f4f0df}', s)
        self.assertIn('body.academy-page header{background:#252b19;border-bottom:4px solid var(--gold)}', s)
        self.assertIn('body.academy-page .topline{background:#252b19;border-bottom:3px solid var(--gold)}', s)
        self.assertIn('body.academy-page main>.hero,body.academy-page main>.section,body.academy-page main>.metrics{border:4px solid var(--gold);margin:14px 0;background:#252b19}', s)
        self.assertIn('body.academy-page .section.alt{background:#252b19}', s)
        self.assertIn('body.academy-page footer{width:min(1240px,calc(100% - 24px));margin:0 auto 16px;border:4px solid var(--gold);background:#252b19}', s)
        for old in (
            'body.academy-page .section.alt{background:#202617}',
            'body.academy-page footer{width:min(1240px,calc(100% - 24px));margin:0 auto 16px;border:4px solid var(--gold);background:#202617}',
            'background:linear-gradient(145deg,#252b19,#202617)',
        ):
            self.assertNotIn(old, s)
        self.assertIn('body.academy-page .faq-item{border-bottom:2px solid var(--gold)}', s)

    def test_never_touch_homepage_in_this_color_correction(self):
        source = ROOT / "public/index.html"
        self.assertTrue(source.exists())
        # Homepage remains exempt from color-unification; no new stylesheet
        # is appended to the original homepage.
        homepage = source.read_text(encoding="utf8")
        self.assertNotIn('zomorod-interior-palette-readonly-20261114.yml', homepage)
        self.assertNotIn('zm-interior-olive-palette-readonly', homepage)


if __name__ == "__main__":
    unittest.main()
