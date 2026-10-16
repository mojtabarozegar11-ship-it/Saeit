"""Regression guards for the fully rebuilt MojPlayWin Atelier V4 pages.

This test suite does not deploy or change shared routes or protected subsites.
"""
from pathlib import Path
from django.test import TestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]
THEMES = ROOT / "core" / "templates" / "mojplaywin"


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinAtelierV4Tests(TestCase):
    def test_new_template_replaces_old_embedded_visual_engine(self):
        theme = (THEMES / "theme.html").read_text(encoding="utf-8")
        self.assertIn('data-design="mojplaywin-atelier-v4"', theme)
        self.assertIn('data-design="atelier-v4"', theme)
        self.assertIn('id="mw-all-pages-menu"', theme)
        self.assertIn('site/mojplaywin-brand.jpg', theme)
        self.assertIn("mpx-feature-grid", theme)
        self.assertIn("prefers-reduced-motion:reduce", theme)
        self.assertIn("prefers-contrast:more", theme)
        self.assertNotIn("data:image/jpeg;base64", theme)

    def test_new_site_sections_preserve_all_original_editorials_and_directory(self):
        home = (THEMES / "home.html").read_text(encoding="utf-8")
        self.assertIn('class="mpx-hero"', home)
        self.assertIn('class="mpx-feature-grid"', home)
        self.assertIn('class="mpx-priorities"', home)
        self.assertIn('id="site-directory"', home)
        self.assertIn("All MojPlayWin pages", home)
        self.assertIn("OUR PORTFOLIO · 80%", home)
        self.assertIn("CONNECTED VENTURES · 20%", home)
        self.assertEqual(home.count('id="home-guide-'), 10)
        self.assertIn('{% for item in features %}', home)
        self.assertIn('{% for item in ventures %}', home)
        self.assertIn("{{ item.url }}", home)

    def test_store_and_venture_context_remain_dynamic(self):
        store = (THEMES / "store.html").read_text(encoding="utf-8")
        section = (THEMES / "section.html").read_text(encoding="utf-8")
        self.assertIn('{{ products|length }}', store)
        self.assertIn('{{ product.title }}', store)
        self.assertIn('{{ product.url }}', store)
        self.assertIn("INITIAL COLLECTION", store)
        self.assertIn('{{ section_title }}', section)
        self.assertIn('{{ section_lead }}', section)
        self.assertIn('{{ section_note }}', section)
        self.assertIn('mw-page-hero', section)
        self.assertIn('Explore connected fields', section)
        self.assertIn('{% if item.slug != active_venture %}', section)

    def test_public_main_domain_pages_render_new_theme_with_old_urls(self):
        samples = [("/", "mpx-feature-grid"), ("/store/", "mpx-catalog"),
                   ("/ventures/agriculture/", "mpx-inner-grid")]
        for url, marker in samples:
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertIn("mojplaywin-atelier-v4", html)
                self.assertIn(marker, html)

    def test_zomorod_root_does_not_receive_new_theme(self):
        response = self.client.get("/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mojplaywin-atelier-v4", response.content.decode("utf-8"))
