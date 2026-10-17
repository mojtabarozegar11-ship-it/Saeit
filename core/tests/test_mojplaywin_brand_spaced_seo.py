"""Main-domain Moj Play Win spelling and machine-readable brand identity SEO.

Review brand name, no URL changes, no title stuffing, no content deletions,
and no reads or writes to protected subsite storage.
"""
import json
import re
from pathlib import Path
from django.test import SimpleTestCase, override_settings

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"

@override_settings(
    ROOT_URLCONF="core.mojplaywin_atelier_preview_urls",
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"],
)
class MojPlayWinSpacedNameSEOTests(SimpleTestCase):
    def test_spaced_brand_is_primary_title_h1_and_meta_description(self):
        r = self.client.get("/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn("<title>Moj Play Win | Games, AI, Research & Digital Products</title>", html)
        self.assertIn('<h1 id="mw-home-title">Moj <em>Play</em> Win</h1>', html)
        self.assertIn('Moj Play Win (MojPlayWin) brings together', html)
        self.assertIn('property="og:site_name" content="Moj Play Win"', html)
        self.assertIn('name="twitter:title" content="Moj Play Win', html)
        self.assertIn('rel="canonical" href="https://mojplaywin.com/"', html)
        self.assertNotIn("noindex,nofollow,noarchive", html)
        self.assertEqual(html.count('id="mw-home-title"'), 1)
        self.assertEqual(html.count('class="mpo-orbit-card"'), 18)
        self.assertEqual(html.count('class="mpo-ring"'), 3)
        self.assertEqual(html.count('id="home-guide-'), 10)
        self.assertIn("© 2022 MojPlayWin. All rights reserved.", html)

    def test_schema_organization_and_website_use_spaced_name_and_alias(self):
        html = self.client.get("/", HTTP_HOST="mojplaywin.com").content.decode()
        payloads = re.findall(r'<script type="application/ld\+json">([^<]+)</script>', html)
        documents = [json.loads(p) for p in payloads]
        graphs = [x for d in documents for x in d.get("@graph", [])]
        organization = next(d for d in graphs if d.get("@type") == "Organization")
        website = next(d for d in graphs if d.get("@type") == "WebSite")
        self.assertEqual(organization["name"], "Moj Play Win")
        self.assertIn("MojPlayWin", organization["alternateName"])
        self.assertIn("Moj play win", organization["alternateName"])
        self.assertEqual(website["name"], "Moj Play Win")
        self.assertEqual(website["alternateName"], "MojPlayWin")
        self.assertEqual(organization["url"], "https://mojplaywin.com/")
        self.assertEqual(website["url"], "https://mojplaywin.com/")

    def test_dynamic_main_domain_store_and_ventures_preserve_routes(self):
        store = self.client.get("/store/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(store.status_code, 200)
        self.assertIn("Digital Store | Moj Play Win", store.content.decode())
        agriculture = self.client.get("/ventures/agriculture/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(agriculture.status_code, 200)
        self.assertIn("Agriculture &", agriculture.content.decode())
        self.assertIn(" | Moj Play Win", agriculture.content.decode())
        self.assertIn('href="https://mojplaywin.com/ventures/agriculture/"', agriculture.content.decode())

    def test_legacy_brand_templates_use_primary_spaced_name_without_changing_copyright(self):
        base = (TEMPLATES / "brands/mojplaywin/base.html").read_text(encoding="utf-8")
        page = (TEMPLATES / "brands/mojplaywin/page.html").read_text(encoding="utf-8")
        self.assertIn('content="Moj Play Win"', base)
        self.assertIn('"name":"Moj Play Win","alternateName":"MojPlayWin"', base)
        self.assertIn("{{ page.title }} — Moj Play Win", page)
        self.assertIn("© 2022 MojPlayWin. All rights reserved.", base)
