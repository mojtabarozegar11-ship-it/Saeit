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
