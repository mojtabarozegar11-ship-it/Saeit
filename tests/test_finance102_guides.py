"""Offline, no-Django safety and content coverage tests for all 102 finance pages."""
import unittest
from pathlib import Path
from core.finance102_guides import BRAND_TOPICS, LOCALES, KINDS, guide_for


class Finance102GuidesTest(unittest.TestCase):
    def test_unique_102_complete_guides(self):
        self.assertEqual(len(BRAND_TOPICS), 17)
        self.assertEqual(set(LOCALES), {"fa", "en", "ar"})
        self.assertEqual(set(KINDS), {"signals", "store"})
        guides = [(slug, locale, kind, guide_for(slug, locale, kind))
                  for slug in BRAND_TOPICS for locale in LOCALES for kind in KINDS]
        self.assertEqual(len(guides), 102)
        assert {k for _, _, _, g in guides for k in g} == {
            "intro", "section_label", "steps_heading", "steps", "example_heading", "example"}
        self.assertEqual(len({g["intro"] for _, _, _, g in guides}), 102)
        for slug, locale, kind, guide in guides:
            self.assertTrue(all(len(x) >= 18 for x in guide.values()))
            self.assertNotIn("{topic}", str(guide))
            self.assertIn(BRAND_TOPICS[slug][LOCALES[locale]], guide["steps"])
            self.assertIn("500" if locale == "en" else ("۵۰۰" if locale == "fa" else "٥٠٠"),
                          guide["example"] if kind == "signals" else ("500" if locale == "en" else ("۵۰۰" if locale == "fa" else "٥٠٠")))
            self.assertNotIn("guaranteed profit", guide["intro"].lower())

    def test_unknown_or_unsafe_guide_rejected(self):
        for slug, locale, kind in [
            ("../", "fa", "signals"), ("saman", "ru", "store"), ("saman", "en", "game")
        ]:
            with self.assertRaises(ValueError):
                guide_for(slug, locale, kind)

    def test_existing_template_visual_tokens_preserved(self):
        template = Path("core/templates/core/financial_brand_page.html").read_text("utf-8")
        self.assertIn("{% if finance_guide %}", template)
        self.assertIn("{{ finance_guide.steps_heading }}", template)
        self.assertIn("{{ finance_guide.example }}", template)
        self.assertIn('class="cards"', template)
        self.assertIn("© {{ brand_name }} · MojPlayWin / Zomorod Melal", template)

    def test_existing_finance_routes_preserved(self):
        urls = Path("config/urls.py").read_text("utf-8")
        self.assertIn('f"{_brand_slug}/market-signals/"', urls)
        self.assertIn('f"{_brand_slug}/digital-products/"', urls)
        self.assertIn('f"ar/{_brand_slug}/market-signals/"', urls)
        self.assertIn('f"ar/{_brand_slug}/digital-products/"', urls)

if __name__ == "__main__":
    unittest.main()
