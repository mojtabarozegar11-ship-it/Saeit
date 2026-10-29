"""S-01: archived lesson progress and embargoed newsletter link regressions."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import academy_views, newsletter_views


class AcademyProgressTests(SimpleTestCase):
    def test_archived_lessons_excluded_from_numerator(self):
        lessons = MagicMock()
        lessons.filter.return_value.count.return_value = 3
        progress = MagicMock()
        progress.filter.return_value.count.return_value = 2
        enrollment = SimpleNamespace(
            course=SimpleNamespace(lessons=lessons), progress=progress
        )
        self.assertEqual(academy_views.education_dashboard_progress(enrollment), (3, 2, 67))
        lessons.filter.assert_called_once_with(active=True)
        progress.filter.assert_called_once_with(completed=True, lesson__active=True)

    def test_completion_percentage_capped_and_empty_course_safe(self):
        lessons, progress = MagicMock(), MagicMock()
        lessons.filter.return_value.count.return_value = 3
        progress.filter.return_value.count.return_value = 5
        enrollment = SimpleNamespace(
            course=SimpleNamespace(lessons=lessons), progress=progress
        )
        self.assertEqual(academy_views.education_dashboard_progress(enrollment)[2], 100)
        lessons.filter.return_value.count.return_value = 0
        progress.filter.return_value.count.return_value = 0
        self.assertEqual(academy_views.education_dashboard_progress(enrollment), (0, 0, 0))


class NewsletterEmbargoTests(SimpleTestCase):
    def test_related_links_apply_published_at_visibility_and_order(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        story = SimpleNamespace(
            pk=9, slug="test-story", story_type="research", title="Test",
            summary="Summary", published_at=now, created_at=now,
            updated_at=now, author_name="", image=None,
            publications=MagicMock(),
        )
        manager = MagicMock()
        manager.select_related.return_value.filter.return_value.first.return_value = story
        model = SimpleNamespace(objects=manager)
        with patch.object(newsletter_views, "NewsletterStory", model), \
             patch.object(newsletter_views, "missing_public_tables", return_value=False), \
             patch.object(newsletter_views, "render", return_value=HttpResponse("ok")), \
             patch("django.utils.timezone.now", return_value=now):
            response = newsletter_views.newsletter_detail(
                RequestFactory().get("/newsletter/test-story/"), "test-story"
            )
        self.assertEqual(response.status_code, 200)
        manager.filter.assert_called_once_with(
            status="published", published_at__lte=now, story_type="research"
        )
        manager.filter.return_value.exclude.assert_called_once_with(pk=9)
        manager.filter.return_value.exclude.return_value.order_by.assert_called_once_with(
            "-published_at"
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
