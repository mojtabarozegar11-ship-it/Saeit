"""Regression for the current-main Zomorod office route transition.

The legacy /business/ PHP accounting desk remains independent and unchanged.
The new Django private office must enforce TLS and authenticate before access;
it is not a replacement for the established /company/office/login/ redirect.
"""

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve


class CompanyOfficeRouteTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def anonymous_request(self, secure=True):
        request = self.factory.get("/company/office/", secure=secure)
        request.user = AnonymousUser()
        return request

    def test_office_root_is_private_django_dashboard(self):
        match = resolve("/company/office/")
        self.assertEqual(match.url_name, "dashboard")
        self.assertEqual(match.namespace, "enterprise_portal")

        response = match.func(self.anonymous_request())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith("/company/office/secure-login/"),
            response["Location"],
        )
        self.assertIn("next=", response["Location"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertNotEqual(response["Location"], "/business/")

    def test_office_root_rejects_cleartext(self):
        match = resolve("/company/office/")
        response = match.func(self.anonymous_request(secure=False))
        self.assertEqual(response.status_code, 403)
        self.assertIn("no-store", response["Cache-Control"])

    def test_existing_office_login_route_is_preserved(self):
        match = resolve("/company/office/login/")
        self.assertEqual(match.url_name, "company_office_login")

        response = match.func(self.factory.get("/company/office/login/"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "/admin/login/?next=/staff/command-center/",
        )
