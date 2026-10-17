"""Full independent MojPlayWin web-engineering B2B page prepublication gates."""
from pathlib import Path
from django.test import SimpleTestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "core/templates/mojplaywin/web_engineering.html"


@override_settings(
    ROOT_URLCONF="core.mojplaywin_atelier_preview_urls",
    ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"],
)
class MojPlayWinWebEngineeringTests(SimpleTestCase):
    def test_page_is_complete_and_mojplaywin_only(self):
        data = PAGE.read_text(encoding="utf-8")
        self.assertGreater(len(data), 13500)
        for phrase in (
            "Web application engineering", "Premium website design",
            "Digital commerce systems", "AI-enabled user experiences",
            "Speed, accessibility and SEO", "Recovery and long-term support",
            "Quality you can inspect", "Practical answers before commissioning a project",
            "Start with a precise project brief",
        ):
            with self.subTest(section=phrase):
                self.assertIn(phrase, data)
        self.assertEqual(data.count("class=\"mpw-web-card\""), 6)
        self.assertIn("{% include \"mojplaywin/footer.html\" %}", data)

    def test_mojplaywin_host_renders_real_editorial_page(self):
        for host in ("mojplaywin.com", "www.mojplaywin.com"):
            with self.subTest(host=host):
                response = self.client.get("/web-engineering/", HTTP_HOST=host)
                self.assertEqual(response.status_code, 200)
                text = response.content.decode("utf-8")
                self.assertIn("Web experiences that demonstrate", text)
                self.assertIn("Django applications", text)
                self.assertIn("Canada and the United States", text)
                self.assertIn("© 2022 MojPlayWin", text)
                self.assertIn("site/heroes/services.", text)
                self.assertIn('href="https://mojplaywin.com/web-engineering/"', text)
                self.assertEqual(text.count("<h1"), 1)

    def test_protected_zomorod_site_cannot_render_mojplaywin_business_page(self):
        response = self.client.get("/web-engineering/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 404)

    def test_main_shared_urlconf_remains_untouched_by_the_preview(self):
        routes = (ROOT / "config/urls.py").read_text(encoding="utf-8")
        self.assertNotIn('path("web-engineering/"', routes)
        engine = (ROOT / "core/mojplaywin_web_views.py").read_text(encoding="utf-8")
        self.assertNotIn("Product.objects", engine)
        self.assertNotIn("PaymentIntent.objects", engine)
        self.assertNotIn(".save(", engine)
