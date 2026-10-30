"""S-01 no-DB regression: nullable legacy search and mid-render gallery outage."""
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import seo_views, company_content_views


class NullableSearchSummaryTests(SimpleTestCase):
    def test_null_legacy_article_content_is_not_a_public_500(self):
        article = SimpleNamespace(title="synthetic-nullable", content=None, slug="sample")
        with patch.object(seo_views, "NewsletterStory") as stories, \
             patch.object(seo_views, "KnowledgeArticle") as articles, \
             patch.object(seo_views, "KnowledgeBook") as books, \
             patch.object(seo_views, "KnowledgeDomain") as domains, \
             patch.object(seo_views, "Product") as products, \
             patch.object(seo_views, "render", return_value=HttpResponse("ok")) as renderer:
            stories.objects.filter.return_value.filter.return_value.__getitem__.return_value = []
            articles.objects.filter.return_value.filter.return_value.__getitem__.return_value = [article]
            books.objects.filter.return_value.filter.return_value.__getitem__.return_value = []
            domains.objects.filter.return_value.filter.return_value.__getitem__.return_value = []
            products.objects.filter.return_value.filter.return_value.__getitem__.return_value = []
            response = seo_views._site_search_with_schema(
                RequestFactory().get("/search/?q=synthetic-nullable")
            )
        self.assertEqual(response.status_code, 200)
        rows = renderer.call_args.args[2]["results"]
        self.assertEqual(rows[0]["summary"], "")
        self.assertEqual(rows[0]["url"], "/knowledge/article/sample/")


class GalleryRuntimeOutageTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/company-gallery/")

    def test_database_disconnection_during_render_is_retryable_not_empty(self):
        with patch.object(company_content_views, "_company_gallery_with_schema",
                          side_effect=DatabaseError("synthetic internal detail")):
            response = company_content_views.company_gallery(self.request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertNotIn("synthetic internal detail", response.content.decode("utf-8"))
        self.assertIn("گالری", response.content.decode("utf-8"))

    def test_healthy_gallery_preserves_original_renderer(self):
        expected = HttpResponse("existing gallery")
        with patch.object(company_content_views, "_company_gallery_with_schema",
                          return_value=expected):
            self.assertIs(company_content_views.company_gallery(self.request), expected)


class CompanyFeedAndInquiryOutageTests(SimpleTestCase):
    def test_feed_midquery_db_failure_returns_retryable_503(self):
        request = RequestFactory().get("/company/department-1/content/")
        with patch.object(company_content_views, "_company_content_feed_with_schema",
                          side_effect=DatabaseError("private synthetic DB error")):
            response = company_content_views.company_content_feed(request, "department-1")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotIn("private synthetic DB error", response.content.decode("utf-8"))

    def test_inquiry_db_failure_does_not_claim_saved_or_request_blind_retry(self):
        request = RequestFactory().post("/company/", {
            "kind": "general", "name": "Synthetic", "email": "fixture@example.test",
            "subject": "Synthetic", "message": "Synthetic",
        })
        with patch.object(company_content_views, "missing_public_tables", return_value=False), \
             patch.object(company_content_views, "CompanyInquiry") as inquiry:
            inquiry.objects.create.side_effect = DatabaseError("synthetic commit unknown")
            response = company_content_views.company_portal_home(request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertNotIn("synthetic commit unknown", response.content.decode("utf-8"))
        self.assertIn("قابل تأیید نیست", response.content.decode("utf-8"))


class AdvertisedAuthorAvailabilityTests(SimpleTestCase):
    def test_missing_author_static_source_is_retryable_not_search_deindexing_404(self):
        with patch.object(seo_views, "_read_author_html",
                          side_effect=FileNotFoundError("synthetic source missing")):
            response = seo_views.persian_author_profile(
                RequestFactory().get("/authors/mojtaba-rozegar/")
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
