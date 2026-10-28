"""Regression tests for S-01 read-only public catalog fallback.

No schema migrations, order/payment creation, or production database writes.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.template.loader import render_to_string

from core.academy_views import academy
from core.company_content_views import company_gallery
from core.newsletter_views import newsletter_home
from core.public_catalog_guard import missing_public_tables


class PublicCatalogSchemaFallbackTests(SimpleTestCase):
    def setUp(self):
        self.requests = RequestFactory()

    def test_schema_guard_detects_only_required_missing_tables(self):
        first = SimpleNamespace(_meta=SimpleNamespace(db_table="catalog_first"))
        second = SimpleNamespace(_meta=SimpleNamespace(db_table="catalog_second"))
        with patch("core.public_catalog_guard.connection") as db:
            db.introspection.table_names.return_value = ["catalog_first"]
            self.assertTrue(missing_public_tables(first, second))
            self.assertFalse(missing_public_tables(first))
            db.introspection.table_names.assert_called()

    def test_academy_retains_static_tracks_without_catalog_tables(self):
        with patch("core.academy_views.missing_public_tables", return_value=True), patch(
            "core.academy_views.render", return_value=HttpResponse("academy")
        ) as render_mock:
            response = academy(self.requests.get("/academy/"))
        context = render_mock.call_args.args[2]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(context["catalog_temporarily_unavailable"])
        self.assertEqual(context["courses"], [])
        self.assertEqual(len(context["tracks"]), 8)

    def test_gallery_skips_missing_table_and_keeps_query_filters(self):
        with patch("core.company_content_views.missing_public_tables", return_value=True), patch(
            "core.company_content_views.render", return_value=HttpResponse("gallery")
        ) as render_mock:
            response = company_gallery(self.requests.get("/company-gallery/?type=image&q=orchard"))
        context = render_mock.call_args.args[2]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertEqual(context["media"], [])
        self.assertEqual(context["kind"], "image")
        self.assertEqual(context["query"], "orchard")

    def test_newsletter_skips_missing_tables_without_fabricating_stories(self):
        with patch("core.newsletter_views.missing_public_tables", return_value=True) as guard_mock, patch(
            "core.newsletter_views.render", return_value=HttpResponse("newsletter")
        ) as render_mock:
            response = newsletter_home(self.requests.get("/newsletter/"))
        context = render_mock.call_args.args[2]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertEqual(context["stories"], [])
        self.assertEqual(context["sources"], [])
        self.assertEqual(context["publications"], [])
        self.assertIsNone(context["schedule"])
        self.assertTrue(context["catalog_temporarily_unavailable"])
        from core.newsletter_views import Agent
        self.assertIn(Agent, guard_mock.call_args.args)


class PublicCatalogTruthfulTemplateTests(SimpleTestCase):
    """Verify rendered fallback copy does not contradict the outage banner."""

    def test_gallery_degraded_does_not_claim_zero_published_media(self):
        html = render_to_string("core/company_gallery.html", {
            "media": [], "catalog_temporarily_unavailable": True,
        })
        self.assertIn("وضعیت انتشار رسانه‌ها پس از بازیابی سامانه مشخص می‌شود.", html)
        self.assertNotIn("هنوز رسانه‌ای برای انتشار عمومی ثبت نشده است.", html)

    def test_gallery_normal_empty_state_unchanged(self):
        html = render_to_string("core/company_gallery.html", {
            "media": [], "catalog_temporarily_unavailable": False,
        })
        self.assertIn("هنوز رسانه‌ای برای انتشار عمومی ثبت نشده است.", html)

    def test_newsletter_degraded_does_not_claim_zero_stories_or_sources(self):
        html = render_to_string("core/newsletter.html", {
            "stories": [], "sources": [], "catalog_temporarily_unavailable": True,
        })
        self.assertIn("نمایش خبرهای منتشرشده موقتاً امکان‌پذیر نیست.", html)
        self.assertIn("نمایش منابع ثبت‌شده موقتاً امکان‌پذیر نیست.", html)
        self.assertNotIn("هنوز مطلبی برای انتشار عمومی ثبت نشده است.", html)
        self.assertNotIn("منبع بیرونی ثبت نشده است.", html)

    def test_newsletter_normal_empty_state_unchanged(self):
        html = render_to_string("core/newsletter.html", {
            "stories": [], "sources": [], "catalog_temporarily_unavailable": False,
        })
        self.assertIn("هنوز مطلبی برای انتشار عمومی ثبت نشده است.", html)
        self.assertIn("منبع بیرونی ثبت نشده است.", html)
