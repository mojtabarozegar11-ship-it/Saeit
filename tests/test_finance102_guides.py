"""Offline, no-Django safety and content coverage tests for all 102 finance pages."""
import unittest
from pathlib import Path
from hashlib import sha1
from core.finance102_guides import BRAND_TOPICS, BRAND_CASES, LOCALES, KINDS, guide_for, compose_page_copy, canonical_url, locale_from_public_host


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
        blob = b"blob " + str(len(payload)).encode("ascii") + b"\x00" + payload
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

    def test_51_distinct_localized_numeric_case_studies(self):
        self.assertEqual(set(BRAND_CASES), set(BRAND_TOPICS))
        self.assertEqual(len({case for row in BRAND_CASES.values() for case in row}), 51)
        for slug in BRAND_TOPICS:
            for locale in LOCALES:
                case = BRAND_CASES[slug][LOCALES[locale]]
                self.assertGreaterEqual(len(case), 60)
                self.assertIn(case, guide_for(slug, locale, "signals")["example"])
                self.assertIn(case, guide_for(slug, locale, "store")["example"])
        variants = {
            guide_for(slug, locale, kind)["example"]
            for slug in BRAND_TOPICS for locale in LOCALES for kind in KINDS
        }
        self.assertEqual(len(variants), 102)

    def test_102_unique_canonical_urls_and_safe_host_policy(self):
        urls = {canonical_url(slug, locale, kind)
                for slug in BRAND_TOPICS for locale in LOCALES for kind in KINDS}
        self.assertEqual(len(urls), 102)
        for slug in BRAND_TOPICS:
            for kind, path in (("signals", "market-signals"), ("store", "digital-products")):
                self.assertEqual(canonical_url(slug, "fa", kind),
                                 f"https://zomorodmelal.ir/{slug}/{path}/")
                self.assertEqual(canonical_url(slug, "en", kind),
                                 f"https://mojplaywin.com/{slug}/{path}/")
                self.assertEqual(canonical_url(slug, "ar", kind),
                                 f"https://mojplaywin.com/ar/{slug}/{path}/")
        for slug, locale, kind in [
            ("http://attacker.com", "en", "store"),
            ("saman", "xx", "store"), ("saman", "fa", "game")
        ]:
            with self.assertRaises(ValueError):
                canonical_url(slug, locale, kind)
        view = Path("core/financial_brand_pages.py").read_text("utf-8")
        self.assertIn('response["Link"]', view)
        self.assertIn('response["Content-Language"] = locale', view)
        self.assertIn('response["X-Finance102-Editorial-Revision"] = "finance102-20261113-v2"', view)

    def test_host_language_detection_denies_forwarded_and_substring_spoofing(self):
        for host in (
            "zomorodmelal.ir", "www.zomorodmelal.ir",
            "zomorodmelal.ir:443", "ZOMORODMELAL.IR",
            "zomorodmelal.ir.",
        ):
            self.assertEqual(locale_from_public_host(host), "fa")
        for host in (
            "mojplaywin.com", "www.mojplaywin.com",
            "fakezomorodmelal.ir", "zomorodmelal.ir.attacker.tld",
            "zomorodmelal.ir,mojplaywin.com",
            "evil-zomorodmelal.ir", "", None, 123,
        ):
            self.assertEqual(locale_from_public_host(host), "en")
        view = Path("core/financial_brand_pages.py").read_text("utf-8")
        self.assertNotIn("HTTP_X_FORWARDED_HOST", view)
        self.assertIn("locale_from_public_host(host)", view)
        self.assertIn('request.META.get("HTTP_HOST")', view)

    def test_existing_finance_routes_preserved(self):
        urls = Path("config/urls.py").read_text("utf-8")
        self.assertIn('f"{_brand_slug}/market-signals/"', urls)
        self.assertIn('f"{_brand_slug}/digital-products/"', urls)
        self.assertIn('f"ar/{_brand_slug}/market-signals/"', urls)
        self.assertIn('f"ar/{_brand_slug}/digital-products/"', urls)

if __name__ == "__main__":
    unittest.main()
