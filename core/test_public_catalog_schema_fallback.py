"""Regression tests for S-01 read-only public catalog fallback.

No schema migrations, order/payment creation, or production database writes.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.template.loader import render_to_string

from core.academy_views import academy, education_course_detail, education_lesson, education_enroll, education_lesson_complete, education_bookmark
from core.company_content_views import company_gallery, company_content_feed, company_portal_home
from core.newsletter_views import newsletter_home, newsletter_detail, safe_json_ld
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


    def test_company_feed_missing_schema_returns_retryable_503_without_query(self):
        with patch("core.company_content_views.missing_public_tables", return_value=True) as guard, patch(
            "core.company_content_views.CompanyContentLink.objects.filter"
        ) as query:
            response = company_content_feed(self.requests.get("/company/research/"), "research")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("/company/", response.content.decode("utf8"))
        self.assertEqual(len(guard.call_args.args), 3)
        query.assert_not_called()

    def test_company_inquiry_missing_schema_never_accepts_or_writes_submission(self):
        request = self.requests.post("/company/", {
            "kind": "research", "name": "Private Sender", "email": "private@example.invalid",
            "subject": "Private Subject", "message": "Sensitive content",
        })
        with patch("core.company_content_views.missing_public_tables", return_value=True), patch(
            "core.company_content_views.CompanyInquiry.objects.create"
        ) as create:
            response = company_portal_home(request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn(b"Private Sender", response.content)
        self.assertNotIn(b"Sensitive content", response.content)
        create.assert_not_called()

    def test_company_inquiry_healthy_schema_preserves_existing_submission(self):
        request = self.requests.post("/company/", {
            "kind": "research", "name": "Sender", "email": "sender@example.invalid",
            "subject": "Question", "message": "Details",
        })
        with patch("core.company_content_views.missing_public_tables", return_value=False), patch(
            "core.company_content_views.CompanyInquiry.objects.create"
        ) as create, patch("django.contrib.messages.success"), patch(
            "django.shortcuts.redirect", return_value=HttpResponse(status=302)
        ):
            response = company_portal_home(request)
        self.assertEqual(response.status_code, 302)
        create.assert_called_once()


    def test_bookmark_missing_schema_returns_503_before_lookup_or_write(self):
        request = self.requests.post("/education/course/example/lesson/1/bookmark/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch("core.academy_views.missing_public_tables", return_value=True) as guard, patch(
            "core.academy_views.get_object_or_404"
        ) as lookup, patch(
            "core.academy_views.EducationBookmark.objects.create"
        ) as write, patch(
            "core.academy_views.EducationBookmark.objects.filter"
        ) as read:
            response = education_bookmark(request, "example", 1)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(json.loads(response.content)["error"], "education_temporarily_unavailable")
        from core.academy_views import EducationBookmark
        self.assertIn(EducationBookmark, guard.call_args.args)
        lookup.assert_not_called()
        read.assert_not_called()
        write.assert_not_called()

    def test_bookmark_healthy_schema_preserves_existing_toggle(self):
        request = self.requests.post("/education/course/example/lesson/1/bookmark/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch("core.academy_views.missing_public_tables", return_value=False), patch(
            "core.academy_views.get_object_or_404", return_value=SimpleNamespace(id=1, is_free_preview=True)
        ), patch(
            "core.academy_views.EducationBookmark.objects.filter"
        ) as lookup, patch(
            "core.academy_views.EducationBookmark.objects.create",
            return_value=SimpleNamespace(pk=42)
        ) as create:
            lookup.return_value.first.return_value = None
            response = education_bookmark(request, "example", 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["bookmark_id"], 42)
        create.assert_called_once()

    def test_company_inquiry_rejects_invalid_email_and_kind_without_insert(self):
        for kind, email in (("research", "invalid-email"), ("not-a-real-kind", "sender@example.com")):
            request = self.requests.post("/company/", {
                "kind": kind, "name": "Sender", "email": email,
                "subject": "Question", "message": "Details",
            })
            with patch("core.company_content_views.missing_public_tables", return_value=False), patch(
                "core.company_content_views.CompanyInquiry.objects.create"
            ) as create, patch("django.contrib.messages.error") as error, patch(
                "django.shortcuts.redirect", return_value=HttpResponse(status=302)
            ):
                response = company_portal_home(request)
            self.assertEqual(response.status_code, 302)
            error.assert_called_once()
            create.assert_not_called()

    def test_company_inquiry_rejects_oversized_subject_before_insert(self):
        request = self.requests.post("/company/", {
            "kind": "research", "name": "Sender", "email": "sender@example.com",
            "subject": "X" * 301, "message": "Details",
        })
        with patch("core.company_content_views.missing_public_tables", return_value=False), patch(
            "core.company_content_views.CompanyInquiry.objects.create"
        ) as create, patch("django.contrib.messages.error"), patch(
            "django.shortcuts.redirect", return_value=HttpResponse(status=302)
        ):
            response = company_portal_home(request)
        self.assertEqual(response.status_code, 302)
        create.assert_not_called()


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

    def test_jsonld_cannot_break_out_of_script_tag(self):
        hostile = "</script><img src=x onerror=alert(1)>&"
        encoded = safe_json_ld({"headline": hostile, "description": "خبر واقعی"})
        self.assertNotIn("</script>", encoded)
        self.assertNotIn("<img", encoded)
        self.assertIn("\\u003c", encoded)
        self.assertEqual(json.loads(encoded)["headline"], hostile)

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

    def test_paid_course_enrollment_does_not_mutate_when_rights_tables_missing(self):
        request = self.requests.post("/education/course/example/enroll/")
        request.user = SimpleNamespace(is_authenticated=True)
        paid_course = SimpleNamespace(is_free=False)
        with patch("core.academy_views.missing_public_tables", side_effect=[False, True]) as guard, patch(
            "core.academy_views.get_object_or_404", return_value=paid_course
        ) as lookup, patch("core.academy_views.EducationEnrollment.objects.get_or_create") as mutate, patch(
            "core.academy_views.Order.objects.filter"
        ) as payment_query:
            response = education_enroll(request, "example")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertEqual(json.loads(response.content)["error"], "education_temporarily_unavailable")
        from core.academy_views import Order, OrderItem, Product, EducationCourse, EducationEnrollment
        self.assertEqual(guard.call_count, 2)
        self.assertEqual(guard.call_args_list[0].args, (EducationCourse, EducationEnrollment))
        self.assertEqual(guard.call_args_list[1].args, (Product, Order, OrderItem))
        lookup.assert_called_once()
        mutate.assert_not_called()
        payment_query.assert_not_called()

    def test_free_course_enrollment_does_not_require_payment_schema(self):
        request = self.requests.post("/education/course/free-example/enroll/")
        request.user = SimpleNamespace(is_authenticated=True)
        course = SimpleNamespace(is_free=True)
        enrollment = SimpleNamespace(pk=123)
        with patch("core.academy_views.missing_public_tables", return_value=False) as guard, patch(
            "core.academy_views.get_object_or_404", return_value=course
        ), patch("core.academy_views.EducationEnrollment.objects.get_or_create",
                 return_value=(enrollment, True)) as create, patch(
            "core.academy_views.Order.objects.filter"
        ) as payment_query:
            response = education_enroll(request, "free-example")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["enrollment_id"], 123)
        guard.assert_called_once()
        payment_query.assert_not_called()
        create.assert_called_once()

    def test_lesson_completion_does_not_write_when_progress_table_missing(self):
        request = self.requests.post("/education/course/example/lesson/1/complete/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch("core.academy_views.missing_public_tables", return_value=True) as guard, patch(
            "core.academy_views.get_object_or_404"
        ) as lookup, patch("core.academy_views.EducationProgress.objects.get_or_create") as mutate:
            response = education_lesson_complete(request, "example", 1)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("no-store", response["Cache-Control"])
        from core.academy_views import EducationProgress
        self.assertIn(EducationProgress, guard.call_args.args)
        lookup.assert_not_called()
        mutate.assert_not_called()

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


class PublicCatalogHealthyPathTests(SimpleTestCase):
    """No-DB checks that a full required-table set keeps existing read paths."""

    def setUp(self):
        self.requests = RequestFactory()

    def test_all_required_table_names_preserve_normal_branch(self):
        from core.academy_views import EducationTrack, EducationCourse
        required = (EducationTrack, EducationCourse)
        with patch("core.public_catalog_guard.connection") as db:
            db.introspection.table_names.return_value = [item._meta.db_table for item in required]
            self.assertFalse(missing_public_tables(*required))
            db.introspection.table_names.assert_called_once_with()

    def test_introspection_connection_error_returns_unavailable_not_empty(self):
        from django.db.utils import OperationalError
        from core.academy_views import EducationCourse
        with patch("core.public_catalog_guard.connection") as db:
            db.introspection.table_names.side_effect = OperationalError("unavailable")
            self.assertTrue(missing_public_tables(EducationCourse))
            db.introspection.table_names.assert_called_once_with()

    def test_introspection_programming_error_also_fails_closed(self):
        from django.db.utils import ProgrammingError
        from core.academy_views import EducationCourse
        with patch("core.public_catalog_guard.connection") as db:
            db.introspection.table_names.side_effect = ProgrammingError("bad schema")
            self.assertTrue(missing_public_tables(EducationCourse))

    def test_academy_complete_schema_preserves_course_search_and_filters(self):
        track = SimpleNamespace(key="agri", title="Agriculture", meta="AGRI", description="Learning")
        course = SimpleNamespace(title="Orchard course")
        course_qs = MagicMock()
        course_qs.select_related.return_value = course_qs
        course_qs.filter.return_value = course_qs
        course_qs.order_by.return_value = course_qs
        course_qs.__getitem__.return_value = [course]
        with (
            patch("core.academy_views.missing_public_tables", return_value=False),
            patch("core.academy_views.EducationTrack.objects.filter", return_value=[track]) as track_query,
            patch("core.academy_views.EducationCourse.objects.filter", return_value=course_qs) as course_query,
            patch("core.academy_views.render", return_value=HttpResponse("healthy academy")) as render_mock,
        ):
            response = academy(self.requests.get("/academy/?q=orchard&track=agri&access=free"))
        context = render_mock.call_args.args[2]
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-ZM-Data-Status", response)
        self.assertFalse(context["catalog_temporarily_unavailable"])
        self.assertEqual(context["tracks"][0]["key"], "agri")
        self.assertEqual(context["courses"], [course])
        track_query.assert_called_once_with(active=True)
        course_query.assert_called_once_with(active=True, approved=True)
        course_qs.select_related.assert_called_once_with("track")
        course_qs.filter.assert_any_call(track__key="agri")
        course_qs.filter.assert_any_call(is_free=True)
        course_qs.order_by.assert_called_once_with("track__sort_order", "title")
        course_qs.__getitem__.assert_called_once_with(slice(None, 100, None))

    def test_gallery_complete_schema_keeps_published_media_and_filtering(self):
        media = SimpleNamespace(title="Orchard photo", target_path="/company/")
        media_qs = MagicMock()
        media_qs.select_related.return_value = media_qs
        media_qs.filter.return_value = media_qs
        media_qs.__getitem__.return_value = [media]
        with (
            patch("core.company_content_views.missing_public_tables", return_value=False),
            patch("core.company_content_views.CompanyGalleryMedia.objects.filter", return_value=media_qs),
            patch("core.company_content_views.render", return_value=HttpResponse("healthy gallery")) as render_mock,
        ):
            response = company_gallery(self.requests.get("/company-gallery/?type=image&q=orchard"))
        context = render_mock.call_args.args[2]
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-ZM-Data-Status", response)
        self.assertFalse(context["catalog_temporarily_unavailable"])
        self.assertEqual(context["media"], [media])
        media_qs.select_related.assert_called_once_with("newsletter_story")
        media_qs.filter.assert_any_call(media_type="image")
        media_qs.filter.assert_any_call(title__icontains="orchard")
        media_qs.__getitem__.assert_called_once_with(slice(None, 100, None))

    def test_newsletter_complete_schema_keeps_existing_public_items(self):
        story, source, publication, schedule = (object() for _ in range(4))
        stories_qs, sources_qs, publications_qs, schedule_qs = (MagicMock() for _ in range(4))
        stories_qs.select_related.return_value = stories_qs
        stories_qs.__getitem__.return_value = [story]
        sources_qs.__getitem__.return_value = [source]
        publications_qs.select_related.return_value = publications_qs
        publications_qs.order_by.return_value = publications_qs
        publications_qs.__getitem__.return_value = [publication]
        schedule_qs.first.return_value = schedule
        with (
            patch("core.newsletter_views.missing_public_tables", return_value=False),
            patch("core.newsletter_views.NewsletterStory.objects.filter", return_value=stories_qs),
            patch("core.newsletter_views.NewsletterSource.objects.filter", return_value=sources_qs),
            patch("core.newsletter_views.NewsletterPublication.objects.filter", return_value=publications_qs) as publication_query,
            patch("core.newsletter_views.NewsletterSchedule.objects.filter", return_value=schedule_qs),
            patch("core.newsletter_views.render", return_value=HttpResponse("healthy newsletter")) as render_mock,
        ):
            response = newsletter_home(self.requests.get("/newsletter/"))
        context = render_mock.call_args.args[2]
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-ZM-Data-Status", response)
        self.assertFalse(context["catalog_temporarily_unavailable"])
        self.assertEqual(context["stories"], [story])
        self.assertEqual(context["sources"], [source])
        self.assertEqual(context["publications"], [publication])
        self.assertIs(context["schedule"], schedule)
        stories_qs.select_related.assert_called_once_with("source", "agent")
        publications_qs.select_related.assert_called_once_with("story")
        publications_qs.order_by.assert_called_once_with("-created_at")
        public_filters = publication_query.call_args.kwargs
        self.assertEqual(public_filters["story__status"], "published")
        self.assertEqual(public_filters["status"], "published")
        self.assertIn("story__published_at__lte", public_filters)
        self.assertIn("published_at__lte", public_filters)


class PublicCatalogQueryBoundsTests(SimpleTestCase):
    """Untrusted GET search values must not generate unbounded database scans."""

    def test_academy_search_is_bounded_even_when_schema_is_unavailable(self):
        with patch("core.academy_views.missing_public_tables", return_value=True), patch(
            "core.academy_views.render", return_value=HttpResponse("academy")
        ) as rendered:
            response = academy(RequestFactory().get("/academy/", {"q": "x" * 20000}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rendered.call_args.args[2]["course_q"], "x" * 120)

    def test_gallery_search_is_bounded_even_when_schema_is_unavailable(self):
        with patch("core.company_content_views.missing_public_tables", return_value=True), patch(
            "core.company_content_views.render", return_value=HttpResponse("gallery")
        ) as rendered:
            response = company_gallery(RequestFactory().get("/company-gallery/", {"q": "x" * 20000}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rendered.call_args.args[2]["query"], "x" * 120)
