"""S-01: mid-render DB outages must not become 500s or pretend empty data."""
from unittest.mock import patch

from django.db import DatabaseError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import academy_views, newsletter_views


class MidRenderDatabaseFailureTests(SimpleTestCase):
    def setUp(self):
        self.requests = RequestFactory()

    def assert_retryable_outage(self, response):
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("role=\"status\"", response.content.decode("utf-8"))

    def test_newsletter_home_mid_render_database_error(self):
        with patch.object(newsletter_views, "_newsletter_home_with_schema",
                          side_effect=DatabaseError("redacted")):
            response = newsletter_views.newsletter_home(
                self.requests.get("/newsletter/")
            )
        self.assert_retryable_outage(response)
        self.assertNotIn("redacted", response.content.decode("utf-8"))

    def test_newsletter_archive_uses_same_safe_fallback(self):
        with patch.object(newsletter_views, "_newsletter_home_with_schema",
                          side_effect=DatabaseError):
            response = newsletter_views.newsletter_archive(
                self.requests.get("/newsletter/archive/")
            )
        self.assert_retryable_outage(response)

    def test_newsletter_healthy_response_unchanged(self):
        expected = HttpResponse("existing newsletter")
        with patch.object(newsletter_views, "_newsletter_home_with_schema",
                          return_value=expected):
            self.assertIs(
                newsletter_views.newsletter_home(self.requests.get("/newsletter/")),
                expected,
            )

    def test_academy_mid_render_database_error(self):
        with patch.object(academy_views, "_academy_with_schema",
                          side_effect=DatabaseError("redacted")):
            response = academy_views.academy(self.requests.get("/academy/"))
        self.assert_retryable_outage(response)
        self.assertNotIn("redacted", response.content.decode("utf-8"))

    def test_education_alias_uses_same_safe_fallback(self):
        with patch.object(academy_views, "_academy_with_schema",
                          side_effect=DatabaseError):
            response = academy_views.education(self.requests.get("/education/"))
        self.assert_retryable_outage(response)

    def test_academy_healthy_response_unchanged(self):
        expected = HttpResponse("existing academy")
        with patch.object(academy_views, "_academy_with_schema",
                          return_value=expected):
            self.assertIs(
                academy_views.academy(self.requests.get("/academy/")),
                expected,
            )
