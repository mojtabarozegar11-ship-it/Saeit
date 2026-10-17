"""Fast above-the-fold rendering without deleting any MojPlayWin CSS or pages.

The inline critical styles are byte-identical mirrors of original style files,
so no design drift or accidental loss is permitted. No shared site templates
or runtime files are modified.
"""
from pathlib import Path

from django.test import TestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinInlineStylesTests(TestCase):
    def test_inlined_styles_mirror_protected_original_files_exactly(self):
        pairs = [
            ("core/static/site/mojplaywin-atelier-v4.css",
             "core/templates/brands/mojplaywin/atelier_critical.css"),
            ("core/static/site/mojplaywin-atelier/orbits.css",
             "core/templates/mojplaywin/orbital_critical.css"),
        ]
        for original, inline in pairs:
            with self.subTest(original=original):
                source = (ROOT / original).read_bytes()
                mirror = (ROOT / inline).read_bytes()
                self.assertEqual(source, mirror,
                                 "Inline styles drifted from preserved static source.")
                self.assertGreater(len(source), 2000)

    def test_mojplaywin_home_has_nonblocking_inline_orbital_styles(self):
        home = (ROOT / "core/templates/mojplaywin/home.html").read_text(encoding="utf-8")
        self.assertIn('{% include "mojplaywin/orbital_critical.css" %}', home)
        self.assertNotIn('<link rel="stylesheet" href="{% static \'site/mojplaywin-atelier/orbits.css\' %}">', home)
        response = self.client.get("/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('id="mojplaywin-orbital-inline"', html)
        self.assertIn('class="mpo-orbit-card"', html)
        self.assertIn("© 2022 MojPlayWin", html)

    def test_legacy_brand_pages_inline_without_forcing_external_css_request(self):
        from django.test import override_settings
        base = (ROOT / "core/templates/brands/mojplaywin/base.html").read_text(encoding="utf-8")
        self.assertIn('{% include "brands/mojplaywin/atelier_critical.css" %}', base)
        self.assertNotIn('<link rel="stylesheet" href="{% static \'site/mojplaywin-atelier-v4.css\' %}', base)
        with override_settings(ROOT_URLCONF="core.mojplaywin_atelier_preview_urls"):
            response = self.client.get("/support/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('id="mojplaywin-atelier-v4-inline"', html)
        self.assertIn("Practical help for digital work", html)
        self.assertIn("© 2022 MojPlayWin", html)
