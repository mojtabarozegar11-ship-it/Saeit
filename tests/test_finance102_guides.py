"""Offline, no-Django safety and content coverage tests for all 102 finance pages."""
import unittest
from pathlib import Path
from hashlib import sha1
from core.finance102_guides import BRAND_TOPICS, LOCALES, KINDS, guide_for, compose_page_copy


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
            if kind == "signals":
                self.assertIn({"fa": "۵۰۰", "en": "500", "ar": "٥٠٠"}[locale], guide["example"])
            else:
                self.assertIn({"fa": "۱۳۰", "en": "130", "ar": "١٣٠"}[locale], guide["example"])
            self.assertNotIn("guaranteed profit", guide["intro"].lower())

    def test_unknown_or_unsafe_guide_rejected(self):
        for slug, locale, kind in [
            ("../", "fa", "signals"), ("saman", "ru", "store"), ("saman", "en", "game")
        ]:
            with self.assertRaises(ValueError):
                guide_for(slug, locale, kind)

    def test_existing_live_template_is_exact_main_blob(self):
        payload = Path("core/templates/core/financial_brand_page.html").read_bytes()
        blob = b"blob " + str(len(payload)).encode("ascii") + b"\\x00" + payload
        self.assertEqual(sha1(blob).hexdigest(), "9189b3fc292cad19cd661ad082039a93b8c98d2e")
        self.assertNotIn(b"finance_guide", payload)
        self.assertIn(b'class="cards"', payload)
        self.assertIn("© {{ brand_name }} · MojPlayWin / Zomorod Melal".encode(), payload)

    def test_all_102_guides_render_in_existing_intro_and_notice(self):
        rendered = {}
        for slug in BRAND_TOPICS:
            for locale in LOCALES:
                for kind in KINDS:
                    intro, notice = compose_page_copy(slug, locale, kind, "SOURCE DISCLOSURE.")
                    self.assertIn(BRAND_TOPICS[slug][LOCALES[locale]], intro)
                    self.assertIn("SOURCE DISCLOSURE.", notice)
                    self.assertIn(guide_for(slug, locale, kind)["steps"], notice)
                    self.assertIn(guide_for(slug, locale, kind)["example"], notice)
                    self.assertNotIn("<", notice)
                    rendered[(slug, locale, kind)] = intro
        self.assertEqual(len(rendered), 102)
        self.assertEqual(len(set(rendered.values())), 102)
        for bad in ("", " ", None):
            with self.assertRaises(ValueError):
                compose_page_copy("saman", "fa", "signals", bad)
        view = Path("core/financial_brand_pages.py").read_text("utf-8")
        self.assertIn("intro, notice = compose_page_copy(slug, locale, page_type, notice)", view)
        self.assertNotIn('"finance_guide":', view)

    def test_existing_finance_routes_preserved(self):
        urls = Path("config/urls.py").read_text("utf-8")
        self.assertIn('f"{_brand_slug}/market-signals/"', urls)
        self.assertIn('f"{_brand_slug}/digital-products/"', urls)
        self.assertIn('f"ar/{_brand_slug}/market-signals/"', urls)
        self.assertIn('f"ar/{_brand_slug}/digital-products/"', urls)

if __name__ == "__main__":
    unittest.main()
