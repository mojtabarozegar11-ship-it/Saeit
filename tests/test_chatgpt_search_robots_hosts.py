"""Regression checks for crawler-agnostic search discovery on both public hosts."""
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.seo_views import robots_txt, sitemap_xml
from core.knowledge_agent_models import KnowledgeAgentPlan, KnowledgeBook


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


    def test_public_robots_is_crawler_agnostic(self):
        # Exemplars only: User-agent * is the interoperable rule for all compliant
        # search crawlers, not a fixed allowlist of named AI providers.
        user_agents = (
            "Googlebot", "bingbot", "DuckDuckBot", "Applebot", "YandexBot",
            "Baiduspider", "OAI-SearchBot", "Claude-SearchBot", "PerplexityBot",
        )
        for host in ("zomorodmelal.ir", "mojplaywin.com"):
            baseline = self._body(host)
            for user_agent in user_agents:
                with self.subTest(host=host, user_agent=user_agent):
                    request = RequestFactory().get(
                        "/robots.txt", HTTP_HOST=host, HTTP_USER_AGENT=user_agent,
                    )
                    response = robots_txt(request)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content.decode("utf-8"), baseline)
                    self.assertNotIn("Disallow: /\\n", baseline)


@override_settings(ALLOWED_HOSTS=["zomorodmelal.ir"])
class PublicSitemapCoverageTests(TestCase):
    def test_faremah_services_landing_is_in_company_sitemap(self):
        request = RequestFactory().get("/sitemap.xml", HTTP_HOST="zomorodmelal.ir")
        response = sitemap_xml(request)
        self.assertEqual(response.status_code, 200)
        for path in (
            "faremah/", "gold/", "vehicles/", "marketing/", "chain-stores/",
        ):
            with self.subTest(path=path):
                expected = f"<loc>https://zomorodmelal.ir/{path}</loc>"
                self.assertIn(expected.encode("utf-8"), response.content)

    def test_noncanonical_or_gated_routes_are_not_advertised(self):
        request = RequestFactory().get("/sitemap.xml", HTTP_HOST="zomorodmelal.ir")
        response = sitemap_xml(request)
        self.assertEqual(response.status_code, 200)
        for path in ("about/", "contact/", "education/", "business/"):
            with self.subTest(path=path):
                noncanonical = f"<loc>https://zomorodmelal.ir/{path}</loc>"
                self.assertNotIn(noncanonical.encode("utf-8"), response.content)

    def test_sitemap_includes_published_books_only(self):
        plan = KnowledgeAgentPlan.objects.create(
            code="seo-publication-test", title="SEO visibility test",
            mission="Test public publication state", goal="Avoid unfinished indexing",
        )
        for status in ("planned", "drafting", "review", "approved", "published"):
            KnowledgeBook.objects.create(
                plan=plan, code=f"seo-{status}-book", title=f"{status} book",
                domain="SEO", objective="Visibility by publication state", status=status,
            )
        request = RequestFactory().get("/sitemap.xml", HTTP_HOST="zomorodmelal.ir")
        response = sitemap_xml(request)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn(
            "<loc>https://zomorodmelal.ir/knowledge/book/seo-published-book/</loc>",
            body,
        )
        for status in ("planned", "drafting", "review", "approved"):
            with self.subTest(status=status):
                self.assertNotIn(
                    f"<loc>https://zomorodmelal.ir/knowledge/book/seo-{status}-book/</loc>",
                    body,
                )
