"""Fail-closed root-mount routing acceptance checks for the private company desk.

These checks never touch the production database or enable message dispatch.
The currently deployed root application is older; release needs separate host
and effective database identity attestation before this code can go live.
"""
from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from django.urls import Resolver404, resolve, reverse


class OfficeRootIntegrationRoutingTests(SimpleTestCase):
    def test_root_office_login_legacy_redirects_to_private_mfa_login(self):
        url = reverse("company_office_login")
        self.assertEqual(url, "/company/office/login/")
        matching = resolve(url)
        self.assertEqual(matching.url_name, "company_office_login")
        result = matching.func(RequestFactory().get(url, secure=True))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"], reverse("enterprise_portal:login"),
        )
        self.assertEqual(result["Location"], "/company/office/secure-login/")
        self.assertNotIn("/admin/login/", result["Location"])
        self.assertNotIn("/staff/command-center/", result["Location"])

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
