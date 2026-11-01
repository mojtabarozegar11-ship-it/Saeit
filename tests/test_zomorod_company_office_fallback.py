"""Cutover contract: private Django office routes replace temporary root fallback.

This test only inspects URL resolver behavior. It never uses a production session,
database, external SMS/email provider or real finance data.
"""
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse


class CompanyOfficeUnifiedRoutingTests(SimpleTestCase):
    def test_office_root_resolves_to_private_dashboard(self):
        match = resolve("/company/office/")
        self.assertEqual(match.url_name, "dashboard")
        self.assertEqual(match.namespace, "enterprise_portal")
        self.assertEqual(reverse("enterprise_portal:dashboard"), "/company/office/")

    def test_login_alias_uses_private_login(self):
        match = resolve("/company/office/login/")
        self.assertEqual(match.url_name, "company_office_login")
        response = match.func(RequestFactory().get("/company/office/login/"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/company/office/secure-login/")

    def test_direct_secure_login_resolves(self):
        match = resolve("/company/office/secure-login/")
        self.assertEqual(match.namespace, "enterprise_portal")
        self.assertEqual(match.url_name, "login")

    def test_messages_and_marketing_are_private_django_routes(self):
        self.assertEqual(resolve("/company/office/messages/").namespace,
                         "company_messaging")
        self.assertEqual(resolve("/company/office/marketing/").namespace,
                         "company_marketing")
