"""No-email TRX checkout URL bridge tests; no transaction or live payment."""
from unittest import mock

from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings

from core.product_seo_views import approved_guest_checkout_route


@override_settings(
    ALLOWED_HOSTS=("mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"),
    MPW_TRX_PUBLIC_PRODUCT_IDS=(72, 225, 879),
    MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True,
)
class MPWGuestCheckoutBridgeTests(SimpleTestCase):
    PATH = "/store/product/72/checkout/"

    def test_no_reviewed_backend_returns_clear_503_without_invoice(self):
        with mock.patch(
            "core.mpw_trx_checkout_bridge._reviewed_checkout", return_value=None
        ):
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"No invoice was created", response.content)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    @override_settings(MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False)
    def test_public_gate_off_keeps_checkout_disabled_without_importing_backend(self):
        with mock.patch("core.mpw_trx_checkout_bridge._reviewed_checkout") as backend:
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
            from core.mpw_trx_checkout_bridge import backend_ready
            self.assertFalse(backend_ready())
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"No invoice was created", response.content)
        backend.assert_not_called()

    def test_non_mojplaywin_host_cannot_open_trx_checkout(self):
        with mock.patch("core.mpw_trx_checkout_bridge._reviewed_checkout") as backend:
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="zomorodmelal.ir"
            )
        self.assertEqual(response.status_code, 404)
        backend.assert_not_called()

    def test_non_allowlisted_product_is_rejected_before_backend_load(self):
        with mock.patch("core.mpw_trx_checkout_bridge._reviewed_checkout") as backend:
            response = self.client.get(
                "/store/product/991/checkout/", secure=True,
                HTTP_HOST="mojplaywin.com",
            )
        self.assertEqual(response.status_code, 404)
        backend.assert_not_called()

    def test_insecure_http_does_not_delegate_to_payment(self):
        with mock.patch("core.mpw_trx_checkout_bridge._reviewed_checkout") as backend:
            response = self.client.get(
                self.PATH, secure=False, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 404)
        backend.assert_not_called()

    def test_checkout_page_rejects_post_and_never_creates_order(self):
        with mock.patch("core.mpw_trx_checkout_bridge._reviewed_checkout") as backend:
            response = self.client.post(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 405)
        backend.assert_not_called()

    def test_matching_guest_handler_is_delegated_without_reimplementation(self):
        calls = []

        def reviewed_view(request, product_id):
            calls.append((request.get_host(), product_id))
            return HttpResponse("GUEST_HANDLER_AUTHORITATIVE", status=200)

        with mock.patch(
            "core.mpw_trx_checkout_bridge._reviewed_checkout",
            return_value=reviewed_view,
        ):
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [("mojplaywin.com", 72)])
        self.assertIn(b"GUEST_HANDLER_AUTHORITATIVE", response.content)

    def test_product_cta_requires_verified_guest_backend(self):
        with mock.patch(
            "core.product_seo_views.bridge_backend_ready", return_value=False
        ):
            self.assertIsNone(approved_guest_checkout_route(72))
        with mock.patch(
            "core.product_seo_views.bridge_backend_ready", return_value=True
        ):
            self.assertEqual(approved_guest_checkout_route(72), self.PATH)

    def test_private_backend_import_crash_is_an_explicit_503_not_public_500(self):
        from core import mpw_trx_checkout_bridge as bridge

        with mock.patch.object(
            bridge, "import_module", side_effect=RuntimeError("PRIVATE_DETAILS")
        ):
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"PRIVATE_DETAILS", response.content)

    def test_unreviewed_payment_form_never_counts_as_ready(self):
        from core import mpw_trx_checkout_bridge as bridge

        class Unreviewed:
            product_checkout = staticmethod(lambda request, product_id: HttpResponse())

        with mock.patch.object(bridge, "import_module", return_value=Unreviewed):
            self.assertFalse(bridge.backend_ready())


