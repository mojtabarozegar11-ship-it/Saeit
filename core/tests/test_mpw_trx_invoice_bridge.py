"""Real Django route/CSRF checks for delegated native TRX invoice creation.

These tests never call a real private backend, create orders, or send TRX.
"""
from types import SimpleNamespace
from unittest import mock

from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import resolve

from core import mpw_trx_invoice_bridge as bridge


def installed_backend(calls=None):
    def patched_start(request, product_id):
        if calls is not None:
            calls.append((request.method, request.get_host(), product_id))
        return HttpResponse("OWNER_REVIEWED_INVOICE_HANDLER", status=303)
    patched_start.__name__ = "start_order"
    patched_start.__module__ = "services.mpw_trx_guest_commerce"
    return SimpleNamespace(
        _mpw_guest_checkout_installed=True,
        COMMERCIAL_URLPATTERNS=((bridge.START_ROUTE, patched_start),),
    )


@override_settings(
    ALLOWED_HOSTS=("mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"),
    MPW_TRX_PUBLIC_PRODUCT_IDS=(72, 225, 879),
    MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True,
)
class MPWTrxInvoiceStartBridgeTests(SimpleTestCase):
    PATH = "/commerce/trx-easy/start/72/"

    def test_route_exactly_resolves_to_guarded_bridge(self):
        match = resolve(self.PATH)
        self.assertIs(match.func.__wrapped__.__wrapped__.__wrapped__, bridge.start_order.__wrapped__.__wrapped__.__wrapped__)
        self.assertEqual(match.kwargs, {"product_id": 72})

    def test_uninstalled_backend_returns_503_without_creating_invoice(self):
        with mock.patch.object(bridge, "import_module", side_effect=ImportError):
            response = self.client.post(self.PATH, secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"No invoice was created", response.content)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_wrong_domain_stays_404_before_backend_load(self):
        with mock.patch.object(bridge, "import_module") as imp:
            response = self.client.post(
                self.PATH, secure=True, HTTP_HOST="zomorodmelal.ir"
            )
        self.assertEqual(response.status_code, 404)
        imp.assert_not_called()

    def test_insecure_http_stays_404(self):
        with mock.patch.object(bridge, "import_module") as imp:
            response = self.client.post(
                self.PATH, secure=False, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 404)
        imp.assert_not_called()

    def test_get_is_never_an_invoice_creation_request(self):
        with mock.patch.object(bridge, "import_module") as imp:
            response = self.client.get(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 405)
        imp.assert_not_called()

    def test_unapproved_sku_or_public_switch_off_does_not_delegate(self):
        with mock.patch.object(bridge, "import_module") as imp:
            response = self.client.post(
                "/commerce/trx-easy/start/991/",
                secure=True, HTTP_HOST="mojplaywin.com",
            )
        self.assertEqual(response.status_code, 503)
        imp.assert_not_called()
        with override_settings(MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False):
            with mock.patch.object(bridge, "import_module") as imp:
                response = self.client.post(
                    self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
                )
        self.assertEqual(response.status_code, 503)
        imp.assert_not_called()

    def test_unpatched_or_ambiguous_route_cannot_receive_invoice(self):
        valid = installed_backend()
        for backend in (
            SimpleNamespace(_mpw_guest_checkout_installed=False,
                            COMMERCIAL_URLPATTERNS=valid.COMMERCIAL_URLPATTERNS),
            SimpleNamespace(_mpw_guest_checkout_installed=True,
                            COMMERCIAL_URLPATTERNS=valid.COMMERCIAL_URLPATTERNS * 2),
            SimpleNamespace(_mpw_guest_checkout_installed=True,
                            COMMERCIAL_URLPATTERNS=(("/unrelated/", lambda request: None),)),
            SimpleNamespace(_mpw_guest_checkout_installed=True,
                            COMMERCIAL_URLPATTERNS=list(valid.COMMERCIAL_URLPATTERNS)),
        ):
            with self.subTest(backend=backend):
                with mock.patch.object(bridge, "import_module", return_value=backend):
                    self.assertFalse(bridge.invoice_start_ready())

    def test_reviewed_handler_receives_exact_product_id_and_host(self):
        calls = []
        with mock.patch.object(
            bridge, "import_module", return_value=installed_backend(calls)
        ):
            response = self.client.post(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(calls, [("POST", "mojplaywin.com", 72)])

    def test_public_post_requires_csrf_when_client_enforces_it(self):
        csrf_client = Client(enforce_csrf_checks=True)
        with mock.patch.object(
            bridge, "import_module", return_value=installed_backend()
        ) as installed:
            response = csrf_client.post(
                self.PATH, secure=True, HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 403)
        installed.assert_not_called()

    def test_raw_start_handler_without_guest_wrapper_is_not_approved(self):
        def start_order(request, product_id):
            return HttpResponse("UNPATCHED")
        unreviewed = SimpleNamespace(
            _mpw_guest_checkout_installed=True,
            COMMERCIAL_URLPATTERNS=((bridge.START_ROUTE, start_order),),
        )
        with mock.patch.object(bridge, "import_module", return_value=unreviewed):
            self.assertFalse(bridge.invoice_start_ready())

    def test_invoice_view_rejects_csrf_exempt_guest_wrapper(self):
        invalid = installed_backend()
        handler = invalid.COMMERCIAL_URLPATTERNS[0][1]
        handler.csrf_exempt = True
        with mock.patch.object(bridge, "import_module", return_value=invalid):
            self.assertFalse(bridge.invoice_start_ready())
