from xml.etree import ElementTree

from django.test import TestCase

from core.blog_models import BlogPage


class SitemapRegressionTests(TestCase):
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    def read_sitemap_locations(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.content)
        return [
            node.text
            for node in root.findall("s:url/s:loc", self.namespace)
        ]

    def test_sitemap_includes_public_platform_sections_without_duplicate_archive(self):
        locations = self.read_sitemap_locations()
        for path in (
            "/education/",
            "/weather/",
            "/economy/",
            "/studio/",
        ):
            with self.subTest(path=path):
                self.assertIn(f"https://zomorodmelal.ir{path}", locations)
        self.assertNotIn("https://zomorodmelal.ir/newsletter/archive/", locations)
        self.assertEqual(len(locations), len(set(locations)))

    def test_service_hub_count_matches_the_fourteen_listed_paths(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SERVICES<br><strong>14</strong>")

    def test_studio_has_its_own_topic_page_not_the_contact_fallback(self):
        response = self.client.get("/studio/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "class=\"lux-hero studio-hero\"")
        self.assertContains(response, "استودیو؛ از ایده تا محصول دیجیتال")
        self.assertNotContains(response, "contact-hero")

    def test_sitemap_escapes_dynamic_blog_paths_as_valid_xml(self):
        BlogPage.objects.create(
            code="research&development",
            title="Research and development",
            slug="research-development",
            active=True,
        )
        locations = self.read_sitemap_locations()
        self.assertIn(
            "https://zomorodmelal.ir/blog/research%26development/",
            locations,
        )
