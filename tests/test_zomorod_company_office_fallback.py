"""Regression coverage for the unpublished Zomorod private office root.

The private Django office has a separate, intentionally blocked release. This
temporary fallback is root-only and must be replaced at a validated cutover.
"""

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve


class CompanyOfficeFallbackTests(SimpleTestCase):
    def test_office_root_redirects_to_existing_business_desk(self):
        match = resolve("/company/office/")
        self.assertEqual(match.url_name, "company_office_fallback")

        response = match.func(RequestFactory().get("/company/office/"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/business/")

    def test_existing_office_login_route_is_preserved(self):
        match = resolve("/company/office/login/")
        self.assertEqual(match.url_name, "company_office_login")

        response = match.func(RequestFactory().get("/company/office/login/"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "/admin/login/?next=/staff/command-center/",
        )
