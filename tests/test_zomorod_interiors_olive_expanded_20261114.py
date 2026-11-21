"""Regression checks for scoped color-only changes in EXISTING inner pages.

No homepage changes, new templates, production writes, forms, or payments.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OLIVE = "#252b19"


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def contrast(a, b):
    def lum(value):
        rgb = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
        return sum(c * w for c, w in zip(channels, (0.2126, 0.7152, 0.0722)))
    values = sorted((lum(a), lum(b)))
    return (values[1] + 0.05) / (values[0] + 0.05)


class InteriorOliveExpansion(unittest.TestCase):
    def test_ghanadi_public_source_has_scoped_palette(self):
        s = source("public/ghanadi/index.html")
        self.assertIn("ZM_INTERIOR_OLIVE_SCOPED_20261114", s)
        self.assertIn('meta name="theme-color" content="#252b19"', s)
        self.assertIn(".topbar,.nav,.business,.story,.digital,.contact,.footer{background:var(--zm-inner-olive);", s)

    def test_ghanadi_django_fallback_has_same_palette(self):
        s = source("core/templates/core/ghanadi.html")
        self.assertIn("ZM_INTERIOR_OLIVE_SCOPED_20261114", s)
        self.assertIn('meta name="theme-color" content="#252b19"', s)
        self.assertIn("main .hero h1,main .section-head h2", s)

    def test_ghanadi_cards_keep_dark_ink_on_light_panels(self):
        for p in ("public/ghanadi/index.html", "core/templates/core/ghanadi.html"):
            with self.subTest(path=p):
                s = source(p)
                self.assertIn("main :is(.card,.income-card,.chart-card,.dig,.filter,.notice,.contactbadge,.stamp,.add,.store-note,.sample-pill,.drawer,.feature-art .float){color:#30271d}", s)
                self.assertIn(".card{background:var(--paper)", s)

    def test_ghanadi_business_modules_still_exist(self):
        static = source("public/ghanadi/index.html")
        django = source("core/templates/core/ghanadi.html")
        for s in (static, django):
            self.assertIn("function card(p)", s)
            self.assertIn("id=\"cart\"", s)
        self.assertIn('id="inquiryPanel"', static)

    def test_cafe_shiraz_scoped_palette(self):
        s = source("public/ghanadi/cafe-shiraz/index.html")
        self.assertIn("ZM_INTERIOR_OLIVE_CAFE_20261114", s)
        self.assertIn('meta name="theme-color" content="#252b19"', s)
        self.assertIn(".top,.nav,.section.alt,.footer{background:#252b19;", s)

    def test_cafe_shiraz_light_form_and_cards_remain_readable(self):
        s = source("public/ghanadi/cafe-shiraz/index.html")
        self.assertIn(":where(.card,.step,.trust div,.faq details,.inquiry-shell){--ink:#332b21;", s)
        self.assertIn(".inquiry-field input,.inquiry-field select,.inquiry-field textarea", s)

    def test_auctions_scoped_to_existing_body_class(self):
        s = source("core/templates/core/auctions.html")
        self.assertIn('{% block body_class %}page-auctions commerce-page{% endblock %}', s)
        self.assertIn('id="zm-auctions-inner-olive-20261114"', s)
        self.assertIn("body.zomorod-olive-site.page-auctions", s)
        self.assertIn('href="/contact/"', s)

    def test_homepage_and_shared_base_are_not_restyled(self):
        for p in ("public/index.html", "core/templates/base.html"):
            s = source(p)
            for marker in ("ZM_INTERIOR_OLIVE_SCOPED_20261114",
                           "ZM_INTERIOR_OLIVE_CAFE_20261114",
                           "zm-auctions-inner-olive-20261114"):
                self.assertNotIn(marker, s)

    def test_accessible_olive_text_contrast(self):
        self.assertGreaterEqual(contrast(OLIVE, "#f4f0df"), 7)
        self.assertGreaterEqual(contrast(OLIVE, "#d9dfcf"), 7)
        self.assertGreaterEqual(contrast(OLIVE, "#f1d68e"), 7)
        self.assertGreaterEqual(contrast("#332b21", "#fffdf8"), 7)

    def test_override_follows_existing_rules_without_replacing_templates(self):
        for p, marker, old in (
            ("public/ghanadi/index.html", "ZM_INTERIOR_OLIVE_SCOPED_20261114", ".business{background:#f8f3e9}"),
            ("core/templates/core/ghanadi.html", "ZM_INTERIOR_OLIVE_SCOPED_20261114", ".business{background:#f8f3e9}"),
            ("public/ghanadi/cafe-shiraz/index.html", "ZM_INTERIOR_OLIVE_CAFE_20261114", ".section.alt{background:#eee4d2}"),
        ):
            with self.subTest(path=p):
                s = source(p)
                self.assertGreater(s.index(marker), s.index(old))
                self.assertEqual(s.count(marker), 1)


if __name__ == "__main__":
    unittest.main()
