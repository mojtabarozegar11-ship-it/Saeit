"""Django tests for private invoice recovery; no payment or live accounts."""
from types import SimpleNamespace
from unittest import mock

from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings
from django.urls import resolve

from core import mpw_trx_purchases_bridge as bridge


def guest_recovery_handler(calls=None):
    def purchases(request):
        if calls is not None:
            calls.append((request.method, request.get_host()))
        return HttpResponse("PRIVATE_GUEST_INVOICE_RECOVERY", status=200)
    purchases.__module__ = "services.mpw_trx_guest_commerce"
    return SimpleNamespace(purchases=purchases)


@override_settings(
    ALLOWED_HOSTS=("mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"),
    MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False,
)
class MPWPrivatePurchasesBridgeTests(SimpleTestCase):
    PATH = "/commerce/trx-easy/purchases/"

    def test_purchase_history_url_resolves_even_when_new_sales_disabled(self):
        match = resolve(self.PATH)
        self.assertIs(match.func, bridge.purchases)
        self.assertEqual(match.kwargs, {})

    def test_no_guest_handler_exposes_no_invoice_details(self):
        with mock.patch.object(bridge, "import_module", side_effect=ImportError):
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"do not pay again", response.content)
        self.assertNotIn(b"invoice_id", response.content)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_wrong_host_and_non_https_do_not_load_private_ledger(self):
        with mock.patch.object(bridge, "import_module") as loader:
            wrong_host = self.client.get(
                self.PATH, secure=True, HTTP_HOST="zomorodmelal.ir"
            )
            non_tls = self.client.get(
                self.PATH, secure=False, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(wrong_host.status_code, 404)
        self.assertEqual(non_tls.status_code, 404)
        loader.assert_not_called()

    def test_post_never_queries_purchases(self):
        with mock.patch.object(bridge, "import_module") as loader:
            response = self.client.post(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 405)
        loader.assert_not_called()

    def test_reviewed_guest_handler_is_used_despite_disabled_new_sales(self):
        calls = []
        with mock.patch.object(
            bridge, "import_module", return_value=guest_recovery_handler(calls)
        ):
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="www.mojplaywin.com"
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PRIVATE_GUEST_INVOICE_RECOVERY", response.content)
        self.assertEqual(calls, [("GET", "www.mojplaywin.com")])

    def test_unreviewed_module_cannot_expose_private_purchases(self):
        for obj in (
            SimpleNamespace(purchases=lambda request: HttpResponse("unsafe")),
            SimpleNamespace(purchases=1),
            SimpleNamespace(),
        ):
            with self.subTest(handler=obj):
                with mock.patch.object(bridge, "import_module", return_value=obj):
                    self.assertIsNone(bridge._reviewed_purchases())

    def test_private_guest_import_error_fails_closed_without_leak(self):
        with mock.patch.object(
            bridge, "import_module", side_effect=RuntimeError("SECRET_CONTEXT")
        ):
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"SECRET_CONTEXT", response.content)
