"""Private-office subapplication regression without network or DB writes."""
from django.test import SimpleTestCase, override_settings
from django.urls import get_script_prefix, resolve, reverse, set_script_prefix


class ZomorodOfficeSidecarRouteTests(SimpleTestCase):
    @override_settings(
        ROOT_URLCONF="office_runtime.urls",
        FORCE_SCRIPT_NAME="/company/office",
    )
    def test_mounted_url_reversals_stay_under_private_base(self):
        # Django applies FORCE_SCRIPT_NAME at WSGI initialization; emulating
        # only the setting override does not reset the global script prefix.
        previous = get_script_prefix()
        set_script_prefix("/company/office/")
        try:
            self.assertEqual(
                reverse("enterprise_portal:login"),
                "/company/office/secure-login/",
            )
            self.assertEqual(
                reverse("enterprise_portal:dashboard"),
                "/company/office/",
            )
            self.assertEqual(
                reverse("company_messaging:inbox"),
                "/company/office/messages/",
            )
            self.assertEqual(
                reverse("company_marketing:dashboard"),
                "/company/office/marketing/",
            )
        finally:
            set_script_prefix(previous)

    @override_settings(ROOT_URLCONF="office_runtime.urls")
    def test_sidecar_resolves_only_its_relative_routes(self):
        self.assertEqual(resolve("/secure-login/").url_name, "login")
        self.assertEqual(resolve("/messages/").url_name, "inbox")
        self.assertEqual(resolve("/marketing/").url_name, "dashboard")
