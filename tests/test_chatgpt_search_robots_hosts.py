"""Regression checks for public ChatGPT Search crawler discovery on both site hosts."""
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.seo_views import robots_txt


@override_settings(ALLOWED_HOSTS=[
    "zomorodmelal.ir", "www.zomorodmelal.ir",
    "mojplaywin.com", "www.mojplaywin.com",
])
class PublicRobotsHostTests(SimpleTestCase):
    def _body(self, host):
        request = RequestFactory().get("/robots.txt", HTTP_HOST=host)
        response = robots_txt(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        body = response.content.decode("utf-8")
        self.assertIn("User-agent: *\n", body)
        self.assertIn("Allow: /\n", body)
        self.assertNotIn("\\n", body)
        return body

    def test_mojplaywin_robots_points_to_its_own_sitemap(self):
        for host in ("mojplaywin.com", "www.mojplaywin.com"):
            with self.subTest(host=host):
                body = self._body(host)
                self.assertIn("Sitemap: https://mojplaywin.com/sitemap.xml\n", body)
                self.assertNotIn("zomorodmelal.ir", body)
                self.assertIn("Disallow: /admin/\n", body)
                self.assertIn("Disallow: /api/\n", body)

    def test_zomorod_robots_preserves_its_public_sitemaps(self):
        for host in ("zomorodmelal.ir", "www.zomorodmelal.ir"):
            with self.subTest(host=host):
                body = self._body(host)
                self.assertIn("Sitemap: https://zomorodmelal.ir/sitemap.xml\n", body)
                self.assertIn("Sitemap: https://zomorodmelal.ir/topics/sitemap.xml\n", body)
                self.assertIn("Sitemap: https://zomorodmelal.ir/ghanadi/sitemap.xml\n", body)
                self.assertNotIn("mojplaywin.com", body)
                self.assertIn("Disallow: /site-heritage/\n", body)
