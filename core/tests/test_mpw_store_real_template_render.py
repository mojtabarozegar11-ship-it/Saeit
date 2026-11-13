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
    def _render_store(self, ready_ids=()):
        request = RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
        request.user = AnonymousUser()
        with patch.dict("sys.modules", {"core.commerce_funnel": None}):
            with patch("command_center.mpw_public.feature_enabled", return_value=False):
                with patch("core.mojplaywin_views._featured_checkout_ids", return_value=frozenset(ready_ids)):
                    return store(request)

    def test_real_store_template_renders_without_optional_analytics(self):
        """Do not mock render(); prevent DB queries through SimpleTestCase."""
        response = self._render_store()
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 2000)
        for path in (b"/store/product/72/", b"/store/product/225/",
                     b"/store/product/879/"):
            self.assertIn(path, response.content)
        for sku in (72, 225, 879):
            self.assertNotIn(
                ("/store/product/%d/checkout/" % sku).encode(), response.content
            )
        self.assertIn(b"Checkout unavailable", response.content)
        self.assertIn(b"TRX checkout is temporarily unavailable", response.content)
        self.assertNotIn(b"No account is required. Checkout accepts native TRX", response.content)

    def test_checkout_cta_requires_per_product_readiness(self):
        response = self._render_store(ready_ids=(72, 879))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/store/product/72/checkout/", response.content)
        self.assertNotIn(b"/store/product/225/checkout/", response.content)
        self.assertIn(b"/store/product/879/checkout/", response.content)
        self.assertEqual(response.content.count(b"Buy securely with TRX"), 2)
        self.assertIn(b"How checkout and delivery work", response.content)
        self.assertNotIn(b"TRX checkout is temporarily unavailable", response.content)

    def test_both_payment_states_render_exactly_one_purchases_link(self):
        destination = b'href="/commerce/trx-easy/purchases/"'
        for ids in ((), (72, 879)):
            with self.subTest(ready_ids=ids):
                response = self._render_store(ready_ids=ids)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content.count(destination), 1)
                if ids:
                    self.assertIn(b"How checkout and delivery work", response.content)
                else:
                    self.assertIn(b"TRX checkout is temporarily unavailable", response.content)

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
        },
    )
    def test_real_store_template_resolves_manifest_assets(self):
        """CI first runs collectstatic; verify production-style static lookup too."""
        response = self._render_store()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/static/site/mojplaywin", response.content)
