"""Canonical domain isolation for all six Moj Play Win pages formerly canonicalized
to zomorodmelal.ir. These tests never modify or deploy a production host.
"""
import re
from pathlib import Path
from django.test import SimpleTestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]
VIEWS = ROOT / "core" / "templates" / "mojplaywin"
BROKEN_IN_PRODUCTION = (
    "/store/",
    "/research/",
    "/company/",
    "/knowledge/",
    "/ventures/agriculture/",
    "/ventures/jewelry-gold/",
)

@override_settings(
    ROOT_URLCONF="core.mojplaywin_atelier_preview_urls",
    ALLOWED_HOSTS=("mojplaywin.com", "www.mojplaywin.com", "testserver"),
)
class MojPlayWinCanonicalIsolationTests(SimpleTestCase):
    def test_all_six_pages_have_only_the_correct_mojplaywin_canonical(self):
        for path in BROKEN_IN_PRODUCTION:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                tags = re.findall(
                    r'<link\s+rel="canonical"\s+href="([^"]+)"[^>]*>',
                    html,
                    re.I,
                )
                self.assertEqual(
                    tags,
                    ["https://mojplaywin.com" + path],
                    "A main-host document must not declare Zomorod Melal as canonical",
                )
                self.assertIn(
                    '<meta property="og:url" content="https://mojplaywin.com'
                    + path + '">',
                    html,
                )
                self.assertEqual(html.count("<h1"), 1)
                self.assertIn("Moj Play Win", html)
                self.assertNotIn("noindex,nofollow,noarchive", html)

    def test_same_canonical_for_www_alias_without_canonicalizing_to_www(self):
        for path in BROKEN_IN_PRODUCTION:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="www.mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    'rel="canonical" href="https://mojplaywin.com' + path + '"',
                    response.content.decode("utf-8"),
                )

    def test_main_only_pages_do_not_extend_the_shared_zomorod_base(self):
        for name in ("section.html", "store.html"):
            source = (VIEWS / name).read_text(encoding="utf-8")
            self.assertTrue(
                source.startswith('{% extends "mojplaywin/base.html" %}'),
                "Main-host templates must inherit the private Moj Play Win base",
            )
            self.assertNotIn('{% extends "base.html" %}', source)
        brand_base = (VIEWS / "base.html").read_text(encoding="utf-8")
        self.assertIn(
            '<link rel="canonical" href="https://mojplaywin.com{{ request.path }}">',
            brand_base,
        )
        self.assertEqual(brand_base.count('rel="canonical"'), 1)
        self.assertNotIn('rel="canonical" href="https://zomorodmelal.ir', brand_base)

    def test_checkout_and_subsite_routing_sources_are_not_in_canonical_patch(self):
        # The main-only canonical fix must not require edits to central URL, app,
        # checkout, payment or Passenger configuration.
        store = (VIEWS / "store.html").read_text(encoding="utf-8")
        section = (VIEWS / "section.html").read_text(encoding="utf-8")
        self.assertIn('{% include "mojplaywin/theme.html" %}', store)
        self.assertIn('{% include "mojplaywin/theme.html" %}', section)
        self.assertIn("{% block content %}", store)
        self.assertIn("{% block content %}", section)
