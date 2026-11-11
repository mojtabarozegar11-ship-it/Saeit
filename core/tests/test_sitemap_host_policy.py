"""Host-bound SEO regression checks: public discovery, never commerce gates."""

from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.seo_views import robots_txt, sitemap_xml


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com"])
class MojPlayWinSitemapHostTests(SimpleTestCase):
    def setUp(self):
        self.requests = RequestFactory()

    def test_django_fallback_sitemap_only_lists_known_mojplaywin_route(self):
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        for host in ("mojplaywin.com", "www.mojplaywin.com"):
            with self.subTest(host=host):
                request = self.requests.get("/sitemap.xml", HTTP_HOST=host)
                response = sitemap_xml(request)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Type"].startswith("application/xml"))
                root = ET.fromstring(response.content)
                self.assertEqual(root.tag, ns + "urlset")
                urls = [node.text for node in root.findall(
                    f"{ns}url/{ns}loc"
                )]
                self.assertEqual(urls, ["https://mojplaywin.com/store/"])
                self.assertNotIn(b"zomorodmelal.ir", response.content)
                self.assertNotIn(b"/store/product/", response.content)

    def test_robots_wildcard_keeps_search_and_ai_crawlers_on_public_store(self):
        request = self.requests.get("/robots.txt", HTTP_HOST="mojplaywin.com")
        response = robots_txt(request)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Sitemap: https://mojplaywin.com/sitemap.xml", body)
        self.assertNotIn("zomorodmelal.ir", body)
        robots = RobotFileParser()
        robots.parse(body.splitlines())
        for crawler in ("Googlebot", "Bingbot", "OAI-SearchBot", "Example-SearchAI"):
            with self.subTest(crawler=crawler):
                self.assertTrue(robots.can_fetch(crawler, "https://mojplaywin.com/store/"))
                self.assertFalse(robots.can_fetch(crawler, "https://mojplaywin.com/admin/"))
                self.assertFalse(robots.can_fetch(crawler, "https://mojplaywin.com/api/"))
