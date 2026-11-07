"""Render the genuine MojPlayWin store template without customer or payment IO."""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.mojplaywin_views import store


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MojPlayWinStoreRealTemplateTests(SimpleTestCase):
    def test_real_store_template_renders_without_optional_analytics(self):
        """Do not mock render(); prevent DB queries through SimpleTestCase."""
        request = RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
        request.user = AnonymousUser()
        with patch.dict("sys.modules", {"core.commerce_funnel": None}):
            with patch("command_center.mpw_public.feature_enabled", return_value=False):
                response = store(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 2000)
        for route in (
            b"/store/product/72/checkout/",
            b"/store/product/225/checkout/",
            b"/store/product/879/",
        ):
            self.assertIn(route, response.content)
