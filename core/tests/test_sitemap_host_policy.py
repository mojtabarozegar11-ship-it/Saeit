"""Host-bound SEO regression checks: public discovery, never commerce gates."""

from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.seo_views import robots_txt, sitemap_xml


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com"])
class MojPlayWinSitemapHostTests(SimpleTestCase):
    def setUp(self):
        self.requests = RequestFactory()

    def test_django_fallback_preserves_all_152_historical_mojplaywin_pages(self):
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        required = {
            "https://mojplaywin.com/store/",
            "https://mojplaywin.com/store/product/72/",
            "https://mojplaywin.com/store/product/225/",
            "https://mojplaywin.com/store/product/879/",
        }
        for host in ("mojplaywin.com", "www.mojplaywin.com"):
            with self.subTest(host=host):
                request = self.requests.get("/sitemap.xml", HTTP_HOST=host)
                response = sitemap_xml(request)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Type"].startswith("application/xml"))
                root = ET.fromstring(response.content)
                self.assertEqual(root.tag, ns + "urlset")
                urls = [node.text for node in root.findall(f"{ns}url/{ns}loc")]
                self.assertEqual(len(urls), 152)
                self.assertEqual(len(set(urls)), 152)
                self.assertTrue(required.issubset(urls))
                self.assertTrue(all(url.startswith("https://mojplaywin.com/") for url in urls))
                self.assertNotIn(b"zomorodmelal.ir", response.content)

    def test_missing_snapshot_returns_503_instead_of_one_page_sitemap(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            with override_settings(BASE_DIR=Path(temporary)):
                response = sitemap_xml(
                    self.requests.get("/sitemap.xml", HTTP_HOST="mojplaywin.com")
                )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "3600")
        self.assertNotIn(b"<urlset", response.content)

    def test_single_page_snapshot_is_rejected_before_http_200(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            file = (Path(temporary) / "docs/seo/evidence/"
                    "mpw-public-152-page-reconstructed-baseline-20261112.xml")
            file.parent.mkdir(parents=True)
            file.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://mojplaywin.com/store/</loc></url></urlset>',
                encoding="utf-8",
            )
            with override_settings(BASE_DIR=Path(temporary)):
                response = sitemap_xml(
                    self.requests.get("/sitemap.xml", HTTP_HOST="www.mojplaywin.com")
                )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"<urlset", response.content)

    def test_cross_host_snapshot_is_rejected(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            file = (Path(temporary) / "docs/seo/evidence/"
                    "mpw-public-152-page-reconstructed-baseline-20261112.xml")
            file.parent.mkdir(parents=True)
            file.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://zomorodmelal.ir/store/</loc></url></urlset>',
                encoding="utf-8",
            )
            with override_settings(BASE_DIR=Path(temporary)):
                response = sitemap_xml(
                    self.requests.get("/sitemap.xml", HTTP_HOST="mojplaywin.com")
                )
        self.assertEqual(response.status_code, 503)

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
