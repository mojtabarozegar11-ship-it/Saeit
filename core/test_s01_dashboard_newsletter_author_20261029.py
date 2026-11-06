"""S-01 targeted regressions: private education dashboard and truthful byline."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from core import academy_views, newsletter_views


class EducationDashboardUnavailableTests(SimpleTestCase):
    def test_missing_dependency_returns_retryable_private_html_without_query(self):
        request = RequestFactory().get("/academy/dashboard/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch.object(academy_views, "missing_public_tables", return_value=True) as guard:
            response = academy_views.education_dashboard(request)
        self.assertEqual(response.status_code, 503)
        self.assertIn("text/html", response["Content-Type"])
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("academy/", response.content.decode("utf8"))
        self.assertEqual(len(guard.call_args.args), 9)


class NewsletterAuthorshipTests(SimpleTestCase):
    def test_article_author_uses_recorded_byline_without_invented_credentials(self):
        byline = newsletter_views.verified_story_author(SimpleNamespace(author_name="Independent Researcher"))
        self.assertEqual(byline, {"@type": "Person", "name": "Independent Researcher"})
        self.assertNotIn("jobTitle", byline)
        self.assertNotIn("url", byline)

    def test_blank_byline_falls_back_to_publisher_not_a_fictitious_person(self):
        byline = newsletter_views.verified_story_author(SimpleNamespace(author_name=" "))
        self.assertEqual(byline["@type"], "Organization")
        self.assertNotIn("jobTitle", byline)

    def test_untrusted_editorial_byline_cannot_close_json_ld_script(self):
        byline = newsletter_views.verified_story_author(
            SimpleNamespace(author_name="A</script><script>alert(1)</script>")
        )
        serialized = newsletter_views.safe_json_ld({"author": byline})
        self.assertNotIn("</script>", serialized)
        self.assertIn(r"\u003c", serialized)


class NewsletterDetailOutageTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/newsletter/sample/")

    def test_missing_schema_is_not_misreported_as_deleted(self):
        with patch.object(newsletter_views, "missing_public_tables", return_value=True):
            response = newsletter_views.newsletter_detail(self.request, "sample")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("حذف", response.content.decode("utf-8"))

    def test_db_failure_after_introspection_is_retryable(self):
        from django.db import DatabaseError
        with patch.object(newsletter_views, "_newsletter_detail_with_schema", side_effect=DatabaseError):
            response = newsletter_views.newsletter_detail(self.request, "sample")
        self.assertEqual(response.status_code, 503)

    def test_healthy_newsletter_detail_response_is_unchanged(self):
        from django.http import HttpResponse
        expected = HttpResponse("healthy article")
        with patch.object(newsletter_views, "_newsletter_detail_with_schema", return_value=expected):
            response = newsletter_views.newsletter_detail(self.request, "sample")
        self.assertIs(response, expected)


if __name__ == "__main__":
    import unittest
    unittest.main()
