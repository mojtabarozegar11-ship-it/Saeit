"""Fail-closed root-mount routing acceptance checks for the private company desk.

These checks never touch the production database or enable message dispatch.
The currently deployed root application is older; release needs separate host
and effective database identity attestation before this code can go live.
"""
from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from django.urls import Resolver404, resolve, reverse


class OfficeRootIntegrationRoutingTests(SimpleTestCase):
    def test_legacy_staff_login_remains_unchanged(self):
        # The existing command-center staff login must not be repurposed
        # during a private-office release.
        url = reverse("company_office_login")
        self.assertEqual(url, "/company/office/login/")
        match = resolve(url)
        self.assertEqual(match.url_name, "company_office_login")
        response = match.func(RequestFactory().get(url, secure=True))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], "/admin/login/?next=/staff/command-center/",
        )

    def test_private_office_login_is_a_distinct_mfa_route(self):
        new_login = reverse("enterprise_portal:login")
        self.assertEqual(new_login, "/company/office/secure-login/")
        match = resolve(new_login)
        self.assertEqual(match.view_name, "enterprise_portal:login")
        self.assertNotEqual(new_login, reverse("company_office_login"))

    def test_root_messages_marketing_and_office_login_resolve_privately(self):
        paths = (
            ("/company/office/secure-login/", "enterprise_portal:login"),
            ("/company/office/messages/", "company_messaging:inbox"),
            ("/company/office/messages/new/", "company_messaging:compose"),
            ("/company/office/marketing/", "company_marketing:dashboard"),
        )
        for path, expected in paths:
            with self.subTest(path=path):
                match = resolve(path)
                self.assertEqual(match.view_name, expected)

    def test_root_mount_has_strict_mfa_and_required_apps(self):
        self.assertIs(settings.COMPANY_OFFICE_REQUIRE_MFA, True)
        for application in (
            "enterprise_portal.apps.EnterprisePortalConfig",
            "company_messaging.apps.CompanyMessagingConfig",
            "company_marketing.apps.CompanyMarketingConfig",
        ):
            with self.subTest(application=application):
                self.assertIn(application, settings.INSTALLED_APPS)

    def test_independent_preflight_not_exposed_by_root_urlconf(self):
        # The private sidecar only serves this prefix in its distinct WSGI app.
        with self.assertRaises(Resolver404):
            resolve("/office-preflight-9ab790b15a42/secure-login/")
