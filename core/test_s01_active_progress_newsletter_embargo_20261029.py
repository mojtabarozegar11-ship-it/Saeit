"""S-01: archived lesson progress and embargoed newsletter link regressions."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import academy_views, newsletter_views, company_content_views


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
        self.assertEqual(academy_views.education_dashboard_progress(enrollment), (3, 3, 100))
        lessons.filter.return_value.count.return_value = 0
        progress.filter.return_value.count.return_value = 0
        self.assertEqual(academy_views.education_dashboard_progress(enrollment), (0, 0, 0))


class AcademyCertificateOutageTests(SimpleTestCase):
    def test_certificate_verification_returns_retryable_503_not_false_404(self):
        with patch.object(academy_views, "missing_public_tables", return_value=True), \
             patch.object(academy_views, "get_object_or_404",
                          side_effect=AssertionError("must not query certificate")):
            response = academy_views.education_certificate(
                RequestFactory().get("/academy/certificate/EDU-TEST/"), "EDU-TEST"
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_certificate_issue_returns_503_before_mutation(self):
        request = RequestFactory().post("/academy/course/test/certificate/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch.object(academy_views, "missing_public_tables", return_value=True), \
             patch.object(academy_views, "get_object_or_404",
                          side_effect=AssertionError("must not query enrollment")), \
             patch.object(academy_views.EducationCertificate.objects, "get_or_create",
                          side_effect=AssertionError("must not issue certificate")):
            response = academy_views.education_issue_certificate(request, "test")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")


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
        story.publications.filter.assert_called_once_with(
            status="published", published_at__lte=now
        )
        story.publications.filter.return_value.order_by.assert_called_once_with("channel")
        manager.filter.assert_called_once_with(
            status="published", published_at__lte=now, story_type="research"
        )
        manager.filter.return_value.exclude.assert_called_once_with(pk=9)
        manager.filter.return_value.exclude.return_value.order_by.assert_called_once_with(
            "-published_at"
        )



class AcademyCompletionArchivedLessonsTests(SimpleTestCase):
    def test_completion_excludes_archived_progress_from_active_total(self):
        course = SimpleNamespace(lessons=MagicMock())
        course.lessons.filter.return_value.count.return_value = 3
        lesson = SimpleNamespace(course=course)
        enrollment = SimpleNamespace(
            progress=MagicMock(), status="active", save=MagicMock(),
            completed_at=None,
        )
        enrollment.progress.filter.return_value.count.return_value = 2
        progress = SimpleNamespace(
            completed=False, progress_percent=0, completed_at=None,
            save=MagicMock(),
        )
        request = RequestFactory().post("/academy/course/lesson/complete/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch.object(academy_views, "missing_public_tables", return_value=False), \
             patch.object(academy_views, "get_object_or_404",
                          side_effect=[course, lesson, enrollment]), \
             patch.object(academy_views.EducationProgress.objects, "get_or_create",
                          return_value=(progress, True)):
            response = academy_views.education_lesson_complete(
                request, "course", 7
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(__import__("json").loads(response.content)["course_completed"])
        enrollment.progress.filter.assert_called_once_with(
            completed=True, lesson__active=True
        )
        enrollment.save.assert_not_called()
        progress.save.assert_called_once()


class NewsletterPublicationsPrivacyTests(SimpleTestCase):
    def test_home_lists_only_published_nonembargoed_story_publications(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        publication_manager = MagicMock()
        publication_model = SimpleNamespace(objects=publication_manager)
        with patch.object(newsletter_views, "missing_public_tables", return_value=False), \
             patch.object(newsletter_views, "NewsletterPublication", publication_model), \
             patch.object(newsletter_views, "NewsletterStory", SimpleNamespace(objects=MagicMock())), \
             patch.object(newsletter_views, "NewsletterSource", SimpleNamespace(objects=MagicMock())), \
             patch.object(newsletter_views, "NewsletterSchedule", SimpleNamespace(objects=MagicMock())), \
             patch.object(newsletter_views, "render", return_value=HttpResponse("ok")), \
             patch("django.utils.timezone.now", return_value=now):
            response = newsletter_views.newsletter_home(
                RequestFactory().get("/newsletter/")
            )
        self.assertEqual(response.status_code, 200)
        publication_manager.filter.assert_called_once_with(
            story__status="published", story__published_at__lte=now,
            status="published", published_at__lte=now,
        )
        publication_manager.filter.return_value.select_related.assert_called_once_with("story")
        publication_manager.filter.return_value.select_related.return_value.order_by.assert_called_once_with("-created_at")



class CompanyFeedEmbargoTests(SimpleTestCase):
    def test_company_feed_excludes_future_and_draft_newsletter_links(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        old = SimpleNamespace(status="published", published_at=now)
        future = SimpleNamespace(status="published", published_at=datetime(2026, 10, 30, tzinfo=timezone.utc))
        draft = SimpleNamespace(status="draft", published_at=now)
        old_link = SimpleNamespace(content_type="newsletter", newsletter_story=old, knowledge_article=None)
        future_link = SimpleNamespace(content_type="newsletter", newsletter_story=future, knowledge_article=None)
        draft_link = SimpleNamespace(content_type="newsletter", newsletter_story=draft, knowledge_article=None)
        public_article = SimpleNamespace(
            content_type="knowledge", newsletter_story=None,
            knowledge_article=SimpleNamespace(published=True)
        )
        # A malformed cross-link must not use an unrelated published article
        # to expose a draft story declared as newsletter content.
        mismatched_link = SimpleNamespace(
            content_type="newsletter", newsletter_story=draft,
            knowledge_article=SimpleNamespace(published=True)
        )
        links = MagicMock()
        links.select_related.return_value = [
            future_link, draft_link, mismatched_link, old_link, public_article
        ]
        with patch.object(company_content_views, "missing_public_tables", return_value=False), \
             patch.object(company_content_views.CompanyContentLink.objects, "filter", return_value=links), \
             patch.object(company_content_views.timezone, "now", return_value=now), \
             patch.object(company_content_views, "render", return_value=HttpResponse("ok")) as render_mock:
            response = company_content_views.company_content_feed(
                RequestFactory().get("/company/agriculture/"), "agriculture"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(render_mock.call_args.args[2]["links"], [old_link, public_article])


if __name__ == "__main__":
    import unittest
    unittest.main()
