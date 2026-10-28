"""Regression tests for S-01 read-only public catalog fallback.

No schema migrations, order/payment creation, or production database writes.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.template.loader import render_to_string

from core.academy_views import academy, education_course_detail, education_lesson
from core.company_content_views import company_gallery
from core.newsletter_views import newsletter_home, newsletter_detail
from core.public_catalog_guard import missing_public_tables, mark_public_data_unavailable


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

    def test_degraded_catalog_preserves_indexing_and_normal_response(self):
        normal = HttpResponse("healthy catalog")
        self.assertNotIn("X-Robots-Tag", normal)
        self.assertNotIn("X-ZM-Data-Status", normal)
        degraded = mark_public_data_unavailable(HttpResponse("temporary catalog"))
        self.assertEqual(degraded.status_code, 200)
        self.assertNotIn("X-Robots-Tag", degraded)
        self.assertEqual(degraded["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", degraded["Cache-Control"])
        self.assertNotIn("X-Robots-Tag", normal)

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

    def test_gallery_video_controls_have_accessible_title(self):
        item = SimpleNamespace(
            media_type="video", title="نمونه ویدئو",
            video=SimpleNamespace(url="/media/example.mp4"),
            image=None, research_domain="", description="", target_path="",
        )
        html = render_to_string("core/company_gallery.html", {
            "media": [item], "catalog_temporarily_unavailable": False,
        })
        self.assertIn('aria-label="نمونه ویدئو"', html)
        self.assertIn('src="/media/example.mp4"', html)


class PublicCatalogDetailRouteRegressionTests(SimpleTestCase):
    """Detail pages must not fail with NameError or query missing tables."""

    def setUp(self):
        self.requests = RequestFactory()

    def test_authenticated_course_detail_has_no_undefined_lesson_lookup(self):
        request = self.requests.get("/education/course/example/")
        request.user = SimpleNamespace(is_authenticated=True)
        course = MagicMock()
        course.lessons.filter.return_value = []
        course.resources.filter.return_value = []
        with patch("core.academy_views.missing_public_tables", return_value=False), patch(
            "core.academy_views.get_object_or_404", return_value=course
        ), patch(
            "core.academy_views.EducationEnrollment.objects.filter"
        ) as enrollment_filter, patch(
            "core.academy_views.EducationBookmark.objects.filter"
        ) as bookmark_filter, patch(
            "core.academy_views.render", return_value=HttpResponse("course")
        ) as render_mock:
            enrollment_filter.return_value.first.return_value = None
            response = education_course_detail(request, "example")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(render_mock.call_args.args[1], "core/education_course_detail.html")
        bookmark_filter.assert_not_called()
        self.assertEqual(enrollment_filter.call_args.kwargs["status__in"], ("active", "completed"))

    def test_completed_enrollment_retains_course_and_lesson_read_access(self):
        request = self.requests.get("/education/course/example/lesson/1/")
        request.user = SimpleNamespace(is_authenticated=True)
        course = MagicMock()
        course.slug = "example"
        lesson = SimpleNamespace(id=1, is_free_preview=False)
        course.lessons.filter.return_value = [lesson]
        course.resources.filter.return_value = []
        enrollment = SimpleNamespace(status="completed")
        with patch("core.academy_views.missing_public_tables", return_value=False), patch(
            "core.academy_views.get_object_or_404", side_effect=[course, lesson]
        ), patch(
            "core.academy_views.EducationBookmark.objects.filter"
        ) as bookmark_filter, patch(
            "core.academy_views.EducationEnrollment.objects.filter"
        ) as enrollment_filter, patch(
            "core.academy_views.EducationProgress.objects.filter"
        ) as progress_filter, patch(
            "core.academy_views.render", return_value=HttpResponse("lesson")
        ):
            bookmark_filter.return_value.exists.return_value = False
            enrollment_filter.return_value.first.return_value = enrollment
            progress_filter.return_value.first.return_value = None
            response = education_lesson(request, "example", 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment_filter.call_args.kwargs["status__in"], ("active", "completed"))

    def test_completed_enrollment_hides_invalid_completion_form(self):
        course = SimpleNamespace(slug="example", title="دوره", track=SimpleNamespace(title="آموزش"))
        lesson = SimpleNamespace(id=1, title="درس", summary="", content="متن", duration_minutes=15)
        context = {
            "course": course, "lesson": lesson, "enrollment": SimpleNamespace(status="completed"),
            "lesson_position": 1, "lesson_total": 1, "progress": None,
            "previous_lesson": None, "next_lesson": None, "bookmarked": False,
        }
        html = render_to_string("core/education_lesson.html", context)
        self.assertNotIn("تکمیل این درس", html)
        self.assertIn("ذخیره نشانک", html)
        context["enrollment"] = SimpleNamespace(status="active")
        active_html = render_to_string("core/education_lesson.html", context)
        self.assertIn("تکمیل این درس", active_html)

    def test_course_detail_missing_schema_is_truthful_retryable_503(self):
        with patch("core.academy_views.missing_public_tables", return_value=True) as guard:
            response = education_course_detail(self.requests.get("/education/course/example/"), "example")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("/academy/", response.content.decode("utf-8"))
        from core.academy_views import Product, EducationQuestion
        self.assertIn(Product, guard.call_args.args)
        self.assertIn(EducationQuestion, guard.call_args.args)

    def test_lesson_missing_schema_returns_retryable_503_before_any_lookup(self):
        request = self.requests.get("/education/course/example/lesson/1/")
        request.user = SimpleNamespace(is_authenticated=False)
        with patch("core.academy_views.missing_public_tables", return_value=True) as guard, patch(
            "core.academy_views.get_object_or_404"
        ) as lookup:
            response = education_lesson(request, "example", 1)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("بازگشت به آموزشگاه", response.content.decode("utf-8"))
        lookup.assert_not_called()
        from core.academy_views import EducationEnrollment
        self.assertIn(EducationEnrollment, guard.call_args.args)

    def test_newsletter_detail_missing_schema_is_truthful_retryable_503(self):
        with patch("core.newsletter_views.missing_public_tables", return_value=True) as guard:
            response = newsletter_detail(self.requests.get("/newsletter/example/"), "example")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("/newsletter/", response.content.decode("utf-8"))
        from core.newsletter_views import Agent
        self.assertIn(Agent, guard.call_args.args)

    def test_newsletter_detail_normal_schema_still_returns_real_404(self):
        from django.http import Http404
        with patch("core.newsletter_views.missing_public_tables", return_value=False), patch(
            "core.newsletter_views.NewsletterStory.objects.select_related"
        ) as select_related:
            select_related.return_value.filter.return_value.first.return_value = None
            with self.assertRaises(Http404):
                newsletter_detail(self.requests.get("/newsletter/not-found/"), "not-found")
