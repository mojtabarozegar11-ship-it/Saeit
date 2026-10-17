"""Prevent internal building notes from appearing in public MojPlayWin pages.

Only isolated main-host preview routes are used. No production login,
deployment, orders, payments, protected sites or server modifications.
"""
from pathlib import Path
from django.test import SimpleTestCase, override_settings

BASE = Path(__file__).resolve().parents[2] / "core" / "templates"
OWN = BASE / "mojplaywin"
BRAND = BASE / "brands" / "mojplaywin"

INTERNAL_NOTICES = (
    "Website engineering that speaks for itself. Commercial availability",
    "Pages describe areas of focus and project concepts.",
    "22 Offline page previews",
    "2 Responsive viewports",
    "Initial collection",
    "Browse the existing MojPlayWin catalog without changing product data",
    "Catalog links lead to the relevant MojPlayWin section.",
    "This page describes a professional service framework, not a claim",
    "The destination pages are informational. Contact forms",
    "ENGINEERING REVIEW · EXAMPLE",
    "STATUS: illustration, not a live report",
    "No active farm, livestock facility or product stock",
    "This section is a technical guide. It does not state",
    "Illustration represents a technology concept, not a live agent dashboard",
    "The 80/20 split describes MojPlayWin’s intended portfolio direction;",
    "The 80/20 split is a portfolio direction, not a claim",
)


@override_settings(
    ROOT_URLCONF="core.mojplaywin_atelier_preview_urls",
    ALLOWED_HOSTS=["mojplaywin.com", "localhost", "testserver"],
)
class PublicCopyMustNotShowInternalImplementationNotes(SimpleTestCase):

    def test_every_main_host_rendered_page_is_free_of_build_notes(self):
        pages = (
            "/", "/store/", "/web-engineering/", "/services/",
            "/ventures/agriculture/", "/ventures/jewelry-gold/",
            "/ventures/currency-crypto/", "/ventures/hospitality/",
            "/research/", "/knowledge/", "/studio/", "/agents/",
            "/ai/", "/blockchain/", "/support/",
        )
        for path in pages:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                body = response.content.decode("utf-8")
                for fragment in INTERNAL_NOTICES:
                    self.assertNotIn(fragment, body, f"{path} leaked internal note: {fragment}")

    def test_consumer_content_and_all_navigation_survive(self):
        page = self.client.get("/", HTTP_HOST="mojplaywin.com").content.decode("utf-8")
        self.assertEqual(page.count('class="mpo-orbit-card"'), 18)
        self.assertEqual(page.count('class="mpo-ring"'), 3)
        self.assertEqual(page.count('id="home-guide-'), 10)
        self.assertIn('id="site-directory"', page)
        self.assertIn("MojPlay<em>Win</em>", page)
        self.assertIn("Research, creativity and digital engineering", page)
        self.assertIn("Explore MojPlayWin expertise", page)
        self.assertIn("Original digital play", page)

        store = self.client.get("/store/", HTTP_HOST="mojplaywin.com").content.decode("utf-8")
        self.assertIn("CURATED COLLECTION", store)
        self.assertIn("Explore this collection", store)
        self.assertIn("Digital Store", store)

        educational = self.client.get(
            "/ventures/currency-crypto/", HTTP_HOST="mojplaywin.com"
        ).content.decode("utf-8")
        self.assertIn("No cryptocurrency exchange, custody, brokerage", educational)
        self.assertIn('data-editorial="mojplaywin-original"', educational)
        self.assertEqual(educational.count('class="mpx-editorial-figure"'), 3)

    def test_technical_editorial_notes_remain_in_data_not_template(self):
        from core.mojplaywin_editorial import editorial_for
        editorial = editorial_for("section", "agents")
        self.assertTrue(editorial["note"])
        self.assertIn("does not state that any specific", editorial["note"])

        section = (OWN / "section.html").read_text(encoding="utf-8")
        editorial_template = (OWN / "editorial_experience.html").read_text(encoding="utf-8")
        self.assertNotIn("{{ section_note }}", section)
        self.assertNotIn("{{ editorial.note }}", editorial_template)
        self.assertIn("in editorial.overview", editorial_template)
        self.assertIn("{{ editorial.headline }}", editorial_template)

    def test_original_informative_content_remains_present_in_brand_templates(self):
        home = (BRAND / "home.html").read_text(encoding="utf-8")
        page = (BRAND / "page.html").read_text(encoding="utf-8")
        for source in (home, page):
            self.assertIn("field-", source)
            self.assertIn("guide", source.lower())
        self.assertNotIn("Illustration represents a technology concept, not a live agent dashboard", page)
        self.assertNotIn("not a statement of current revenue or active operations", page)
