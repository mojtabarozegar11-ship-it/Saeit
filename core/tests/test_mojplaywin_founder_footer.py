"""Presentation-only verification of the common gold founder footer on the
Moj Play Win main domain. Independent microsites must keep their own footers.
"""
from pathlib import Path

from django.test import SimpleTestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "core" / "templates"
SIGNATURE = TEMPLATES / "mojplaywin" / "founder_signature.html"
PARTIAL = '{% include "mojplaywin/founder_signature.html" %}'


@override_settings(
    ROOT_URLCONF="core.mojplaywin_atelier_preview_urls",
    ALLOWED_HOSTS=("mojplaywin.com", "www.mojplaywin.com", "testserver"),
)
class MojPlayWinFounderFooterTests(SimpleTestCase):
    def test_both_original_footer_families_use_one_shared_signature(self):
        main = (TEMPLATES / "mojplaywin" / "footer.html").read_text(encoding="utf-8")
        editorial = (TEMPLATES / "brands" / "mojplaywin" / "base.html").read_text(encoding="utf-8")
        self.assertEqual(main.count(PARTIAL), 1)
        self.assertEqual(editorial.count(PARTIAL), 1)
        self.assertIn("</footer>\n" + PARTIAL, main)
        self.assertIn("</footer>\n" + PARTIAL, editorial)
        self.assertIn("© 2022 MojPlayWin. All rights reserved.", main)
        self.assertIn("© 2022 MojPlayWin. All rights reserved.", editorial)

    def test_signage_is_real_accessible_embossed_gold_text_not_an_image(self):
        content = SIGNATURE.read_text(encoding="utf-8")
        self.assertIn('<span class="mpw-founder-name">Mojtaba Roozegar</span>', content)
        self.assertIn(".mpw-founder-name", content)
        self.assertIn("text-shadow:", content)
        self.assertIn("-webkit-text-stroke:", content)
        self.assertIn("font-size:clamp(", content)
        self.assertIn("@media(forced-colors:active)", content)
        for forbidden in ("<script", "<img", "http://", "https://", "fetch(", "checkout", "payment"):
            self.assertNotIn(forbidden, content.lower())

    def test_main_pages_render_exactly_one_gold_founder_signature(self):
        for path in ("/", "/store/", "/research/", "/company/", "/knowledge/", "/services/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(html.count('<span class="mpw-founder-name">Mojtaba Roozegar</span>'), 1)
                self.assertEqual(html.count('id="mpw-founder-plaque-design"'), 1)
                self.assertIn("© 2022 MojPlayWin.", html)
                self.assertEqual(html.count("<h1"), 1)
                self.assertIn('rel="canonical" href="https://mojplaywin.com' + path + '"', html)

    def test_legacy_editorial_template_uses_the_same_signature(self):
        from django.template.loader import render_to_string

        class DummyPage:
            title = "Support"
            kicker = "SUPPORT"
            headline = "How we can help"
            body = "Helpful public information, available to visitors."
            cards = [("Getting started", "SUPPORT", "A clear next step")]

        html = render_to_string(
            "brands/mojplaywin/page.html",
            {"page": DummyPage(), "page_key": "support", "request": None},
        )
        self.assertEqual(html.count('<span class="mpw-founder-name">Mojtaba Roozegar</span>'), 1)
        self.assertIn("Helpful public information", html)
        self.assertIn("© 2022 MojPlayWin.", html)
