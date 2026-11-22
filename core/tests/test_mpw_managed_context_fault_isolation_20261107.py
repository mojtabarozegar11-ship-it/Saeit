"""Safety regression for the MojPlayWin optional managed-content template tag."""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings

from command_center.templatetags.mpw_main import mpw_main_data
from core.mojplaywin_views import store


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MojPlayWinManagedContextFaultIsolationTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get(
            "/store/", secure=True, HTTP_HOST="mojplaywin.com"
        )
        self.request.user = AnonymousUser()

    def test_healthy_managed_context_is_preserved(self):
        expected = {
            "mpw_managed_blocks": [{"title": "Approved sample"}],
            "mpw_managed_offers": [],
        }
        with patch(
            "command_center.templatetags.mpw_main.public_context",
            return_value=expected,
        ) as source:
            self.assertIs(mpw_main_data(self.request), expected)
        source.assert_called_once_with(self.request)

    def test_optional_context_failure_returns_empty_content_without_details(self):
        private_detail = "sensitive-buyer@example.invalid"
        with patch(
            "command_center.templatetags.mpw_main.public_context",
            side_effect=ValueError(private_detail),
        ), self.assertLogs(
            "command_center.templatetags.mpw_main", level="WARNING"
        ) as captured:
            result = mpw_main_data(self.request)

        self.assertEqual(
            result, {"mpw_managed_blocks": [], "mpw_managed_offers": []}
        )
        self.assertNotIn(private_detail, "\n".join(captured.output))
        self.assertIn("ValueError", "\n".join(captured.output))

    def test_public_store_still_renders_if_managed_context_fails(self):
        with patch.dict("sys.modules", {"core.commerce_funnel": None}):
            with patch(
                "command_center.templatetags.mpw_main.public_context",
                side_effect=ValueError("internal-path-should-stay-private"),
            ), self.assertLogs(
                "command_center.templatetags.mpw_main", level="WARNING"
            ):
                response = store(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 2000)
        self.assertIn(b"/store/product/72/checkout/", response.content)
        self.assertIn(b"/store/product/225/checkout/", response.content)
        self.assertNotIn(b"internal-path-should-stay-private", response.content)
