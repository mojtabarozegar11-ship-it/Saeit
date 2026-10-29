"""S-01 regressions: explicit paid-course previews and gallery embargo privacy.

No database writes, payments, migrations or external network requests.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import academy_views, company_content_views


class PaidCoursePreviewTests(SimpleTestCase):
    def _view(self, preview):
        course = SimpleNamespace(is_free=False, lessons=MagicMock())
        lesson = SimpleNamespace(id=7, is_free_preview=preview)
        course.lessons.filter.return_value = [lesson]
        request = RequestFactory().get("/academy/course/paid/lesson/7/")
        request.user = AnonymousUser()
        with patch.object(academy_views, "missing_public_tables", return_value=False), \
             patch.object(academy_views, "get_object_or_404", side_effect=[course, lesson]), \
             patch.object(academy_views, "render", return_value=HttpResponse("preview")) as rendered:
            response = academy_views.education_lesson(request, "paid", 7)
        return response, rendered

    def test_explicit_preview_on_paid_course_is_readable_without_enrollment(self):
        response, rendered = self._view(preview=True)
        self.assertEqual(response.status_code, 200)
        context = rendered.call_args.args[2]
        self.assertIsNone(context["enrollment"])
        self.assertIsNone(context["progress"])
        self.assertEqual(context["lesson_total"], 1)

    def test_unmarked_paid_lesson_still_requires_enrollment(self):
        response, rendered = self._view(preview=False)
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"enrollment_required", response.content)
        rendered.assert_not_called()


class CompanyGalleryEmbargoTests(SimpleTestCase):
    def test_gallery_requires_media_publication_and_linked_story_release(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        queryset = MagicMock()
        with patch.object(company_content_views, "missing_public_tables", return_value=False), \
             patch.object(company_content_views.CompanyGalleryMedia.objects, "filter", return_value=queryset) as base_filter, \
             patch.object(company_content_views.timezone, "now", return_value=now), \
             patch.object(company_content_views, "render", return_value=HttpResponse("gallery")):
            response = company_content_views.company_gallery(RequestFactory().get("/company-gallery/"))
        self.assertEqual(response.status_code, 200)
        base_filter.assert_called_once_with(published=True, published_at__lte=now)
        visibility = queryset.filter.call_args.args[0]
        self.assertEqual(visibility.connector, "OR")
        self.assertIn("newsletter_story__isnull", str(visibility))
        self.assertIn("newsletter_story__status", str(visibility))
        self.assertIn("newsletter_story__published_at__lte", str(visibility))
        queryset.filter.return_value.select_related.assert_called_once_with("newsletter_story")


class PaidBookmarkEntitlementTests(SimpleTestCase):
    def _bookmark(self, preview, enrolled):
        lesson = SimpleNamespace(id=7, is_free_preview=preview, course=SimpleNamespace(pk=4))
        request = RequestFactory().post("/academy/course/paid/lesson/7/bookmark/")
        request.user = SimpleNamespace(is_authenticated=True, pk=9)
        enrollment_qs = MagicMock()
        enrollment_qs.exists.return_value = enrolled
        with patch.object(academy_views, "missing_public_tables", return_value=False), \
             patch.object(academy_views, "get_object_or_404", return_value=lesson), \
             patch.object(academy_views.EducationEnrollment.objects, "filter", return_value=enrollment_qs) as enrollment_filter, \
             patch.object(academy_views.EducationBookmark.objects, "filter") as bookmark_filter, \
             patch.object(academy_views.EducationBookmark.objects, "create") as bookmark_create:
            bookmark_filter.return_value.first.return_value = None
            bookmark_create.return_value.pk = 11
            response = academy_views.education_bookmark(request, "paid", 7)
            return response, enrollment_filter.call_count, bookmark_create.call_count

    def test_nonbuyer_cannot_bookmark_nonpreview_paid_lesson(self):
        response, queried, created = self._bookmark(preview=False, enrolled=False)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(queried, 1)
        self.assertEqual(created, 0)

    def test_completed_enrollment_can_bookmark_paid_lesson(self):
        response, queried, created = self._bookmark(preview=False, enrolled=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queried, 1)
        self.assertEqual(created, 1)

    def test_explicit_free_preview_bookmark_remains_available(self):
        response, queried, created = self._bookmark(preview=True, enrolled=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queried, 0)
        self.assertEqual(created, 1)


class GalleryTargetSafetyTests(SimpleTestCase):
    def test_internal_paths_only(self):
        safe = company_content_views.safe_gallery_target_path
        self.assertEqual(safe("/research/projects/"), "/research/projects/")
        self.assertEqual(safe("/company/?q=1"), "/company/?q=1")
        for unsafe in ("javascript:alert(1)", "https://outside.invalid", "//outside.invalid",
                       "/\\\\outside.invalid", "/\nheader:evil", None, ""):
            with self.subTest(path=unsafe):
                self.assertEqual(safe(unsafe), "")

    def test_percent_encoded_network_paths_and_traversal_fail_closed(self):
        safe = company_content_views.safe_gallery_target_path
        for unsafe in (
            "/%2fexternal.invalid/path", "/%252fexternal.invalid/path",
            "/company/%2e%2e/admin/", "/company/%252e%252e/admin/",
            "/company/%5cexternal.invalid", "/company/%0dheader",
        ):
            with self.subTest(path=unsafe):
                self.assertEqual(safe(unsafe), "")
        self.assertEqual(safe("/company/projects/?q=%2F"), "/company/projects/?q=%2F")
        self.assertEqual(safe("/research/projects/#details"), "/research/projects/#details")

    def test_gallery_view_sets_only_safe_target_for_template(self):
        item = SimpleNamespace(target_path="//outside.invalid")
        queryset = MagicMock()
        queryset.filter.return_value.select_related.return_value.__getitem__.return_value = [item]
        with patch.object(company_content_views, "missing_public_tables", return_value=False), \
             patch.object(company_content_views.CompanyGalleryMedia.objects, "filter", return_value=queryset), \
             patch.object(company_content_views, "render", return_value=HttpResponse("gallery")) as rendered:
            response = company_content_views.company_gallery(RequestFactory().get("/company-gallery/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(item.safe_target_path, "")
        self.assertEqual(rendered.call_args.args[2]["media"], [item])
