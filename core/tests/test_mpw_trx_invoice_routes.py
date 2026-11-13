"""Django routing tests for the private paid-invoice lifecycle.

All handlers are mocked at the commercial boundary; no blockchain, email,
customer account or order is touched.
"""
from types import SimpleNamespace
from unittest import mock

from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import resolve

from core import mpw_trx_invoice_routes as bridge


ROUTES = (
    ("show_invoice", "/commerce/trx-easy/invoice/123/", "GET", {"invoice_id": "123"}),
    ("invoice_status", "/commerce/trx-easy/invoice/123/status/", "GET", {"invoice_id": "123"}),
    ("reconcile_invoice", "/commerce/trx-easy/invoice/123/reconcile/", "POST", {"invoice_id": "123"}),
    ("download_paid", "/commerce/trx-easy/download/receipt-x/", "GET", {"receipt_id": "receipt-x"}),
)


def private_handlers(calls=None):
    pairs = []
    for name, path in bridge.REVIEWED_ROUTES.items():
        def view(request, _calls=calls, _name=name, **kwargs):
            if _calls is not None:
                _calls.append((_name, request.method, kwargs))
            return HttpResponse("ORIGINAL_OWNER_REVIEWED_VIEW", status=200)
        view.__name__ = name
        view.__module__ = "services.mpw_trx_guest_commerce"
        pairs.append((path, view))
    return SimpleNamespace(
        _mpw_guest_checkout_installed=True,
        COMMERCIAL_URLPATTERNS=tuple(pairs),
    )


@override_settings(
    ALLOWED_HOSTS=("mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"),
    MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False,
)
class MPWInvoiceLifecycleBridgeTests(SimpleTestCase):
    def test_every_invoice_lifecycle_route_resolves_exactly(self):
        for name, path, method, kwargs in ROUTES:
            with self.subTest(route=name):
                match = resolve(path)
                self.assertEqual(match.func.__name__, name)
                self.assertEqual(match.kwargs, kwargs)

    def test_uninstalled_private_backend_fails_closed_without_order_details(self):
        for name, path, method, _ in ROUTES:
            with self.subTest(route=name):
                with mock.patch.object(bridge, "import_module", side_effect=ImportError):
                    response = (
                        self.client.post(path, secure=True, HTTP_HOST="mojplaywin.com")
                        if method == "POST" else
                        self.client.get(path, secure=True, HTTP_HOST="mojplaywin.com")
                    )
                self.assertEqual(response.status_code, 503)
                self.assertIn(b"do not send funds again", response.content)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_all_original_guest_handlers_receive_exact_invoice_or_receipt(self):
        calls = []
        with mock.patch.object(
            bridge, "import_module", return_value=private_handlers(calls)
        ):
            for name, path, method, kwargs in ROUTES:
                with self.subTest(name=name):
                    response = (
                        self.client.post(path, secure=True, HTTP_HOST="mojplaywin.com")
                        if method == "POST" else
                        self.client.get(path, secure=True, HTTP_HOST="mojplaywin.com")
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(calls[-1], (name, method, kwargs))
        self.assertEqual(len(calls), 4)

    def test_private_existing_orders_stay_accessible_when_sales_switch_off(self):
        with mock.patch.object(
            bridge, "import_module", return_value=private_handlers()
        ):
            response = self.client.get(
                "/commerce/trx-easy/invoice/123/",
                secure=True, HTTP_HOST="mojplaywin.com",
            )
        self.assertEqual(response.status_code, 200)

    def test_wrong_host_and_cleartext_are_rejected_without_private_import(self):
        with mock.patch.object(bridge, "import_module") as loader:
            for name, path, method, kwargs in ROUTES:
                with self.subTest(route=name):
                    for host, secure in (("zomorodmelal.ir", True),
                                         ("mojplaywin.com", False)):
                        response = (
                            self.client.post(path, secure=secure, HTTP_HOST=host)
                            if method == "POST" else
                            self.client.get(path, secure=secure, HTTP_HOST=host)
                        )
                        self.assertEqual(response.status_code, 404)
        loader.assert_not_called()

    def test_read_endpoints_reject_post_and_reconcile_rejects_get(self):
        with mock.patch.object(bridge, "import_module") as loader:
            for name, path, method, _ in ROUTES:
                response = (
                    self.client.get(path, secure=True, HTTP_HOST="mojplaywin.com")
                    if method == "POST" else
                    self.client.post(path, secure=True, HTTP_HOST="mojplaywin.com")
                )
                self.assertEqual(response.status_code, 405)
        loader.assert_not_called()

    def test_reconciliation_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        with mock.patch.object(bridge, "import_module") as loader:
            response = client.post(
                "/commerce/trx-easy/invoice/123/reconcile/",
                secure=True, HTTP_HOST="mojplaywin.com",
            )
        self.assertEqual(response.status_code, 403)
        loader.assert_not_called()

    def test_duplicate_and_unreviewed_routes_never_delegate(self):
        working = private_handlers()
        for module in (
            SimpleNamespace(
                _mpw_guest_checkout_installed=False,
                COMMERCIAL_URLPATTERNS=working.COMMERCIAL_URLPATTERNS,
            ),
            SimpleNamespace(
                _mpw_guest_checkout_installed=True,
                COMMERCIAL_URLPATTERNS=working.COMMERCIAL_URLPATTERNS * 2,
            ),
            SimpleNamespace(
                _mpw_guest_checkout_installed=True,
                COMMERCIAL_URLPATTERNS=list(working.COMMERCIAL_URLPATTERNS),
            ),
        ):
            with self.subTest(module=module):
                with mock.patch.object(bridge, "import_module", return_value=module):
                    for name in bridge.REVIEWED_ROUTES:
                        self.assertIsNone(bridge._reviewed_handler(name))

    def test_large_opaque_identifiers_do_not_reach_private_backend(self):
        with mock.patch.object(bridge, "import_module") as loader:
            response = self.client.get(
                "/commerce/trx-easy/invoice/" + "a" * 257 + "/",
                secure=True, HTTP_HOST="mojplaywin.com",
            )
        self.assertEqual(response.status_code, 404)
        loader.assert_not_called()
