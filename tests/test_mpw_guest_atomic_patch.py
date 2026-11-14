"""Regression tests for all-or-nothing guest checkout route installation.

Run with Django settings configured: python -m pytest tests/test_mpw_guest_atomic_patch.py
No network, database writes, payments or deployment are performed by these tests.
"""
from django.test import SimpleTestCase, RequestFactory
from django.http import HttpResponse
from unittest.mock import patch, MagicMock

from services.mpw_trx_guest_commerce import patch_commercial


HANDLERS = (
    ("start_order", "_start_order"),
    ("show_invoice", "_show_invoice"),
    ("invoice_status", "_invoice_status"),
    ("reconcile_invoice", "_reconcile_invoice"),
    ("download_paid", "_download_paid"),
)


def _handler(request, *args, **kwargs):
    return None


def _namespace():
    result = {private: _handler for _, private in HANDLERS}
    result.update({public: _handler for public, _ in HANDLERS})
    result["COMMERCIAL_URLPATTERNS"] = (
        ("/commerce/trx-easy/1/start/", _handler),
        ("/commerce/trx-easy/1/invoice/", _handler),
        ("/commerce/trx-easy/1/status/", _handler),
        ("/commerce/trx-easy/1/reconcile/", _handler),
        ("/commerce/trx-easy/1/download/", _handler),
    )
    return result


class GuestAtomicPatchTests(SimpleTestCase):
    def test_guest_cookie_is_sent_on_purchase_recovery_route(self):
        """A checkout cookie must also reach /purchases/ in the same browser."""
        from http.cookies import SimpleCookie
        from services.mpw_trx_guest_commerce import _install_cookie, COOKIE, COOKIE_PATH
        response = _install_cookie(HttpResponse("ok"), "signed-owner-receipt")
        cookie = response.cookies[COOKIE]
        self.assertEqual(COOKIE_PATH, "/")
        self.assertEqual(cookie["path"], "/")
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie.value, "signed-owner-receipt")

    def test_guest_recovery_cookie_remains_noncacheable(self):
        from services.mpw_trx_guest_commerce import _install_cookie
        response = _install_cookie(HttpResponse("ok"), "signed-owner-receipt")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])

    def test_missing_last_handler_leaves_all_routes_untouched(self):
        namespace = _namespace()
        namespace.pop("_download_paid")
        before = {name: namespace[name] for name, _ in HANDLERS}
        patterns = namespace["COMMERCIAL_URLPATTERNS"]
        with self.assertRaisesRegex(RuntimeError, "_download_paid"):
            patch_commercial(namespace)
        for name, original in before.items():
            self.assertIs(namespace[name], original)
        self.assertIs(namespace["COMMERCIAL_URLPATTERNS"], patterns)
        self.assertNotIn("_mpw_guest_checkout_installed", namespace)

    def test_missing_multiple_handlers_lists_all_and_preserves_namespace(self):
        namespace = _namespace()
        namespace.pop("_show_invoice")
        namespace.pop("_download_paid")
        before = namespace.copy()
        with self.assertRaisesRegex(RuntimeError, "_show_invoice.*_download_paid"):
            patch_commercial(namespace)
        self.assertEqual(namespace, before)

    def test_complete_install_replaces_routes_and_is_idempotent(self):
        namespace = _namespace()
        patch_commercial(namespace)
        self.assertTrue(namespace["_mpw_guest_checkout_installed"])
        for name, _ in HANDLERS:
            self.assertIsNot(namespace[name], _handler)
        for (_, view), (name, _) in zip(namespace["COMMERCIAL_URLPATTERNS"], HANDLERS):
            self.assertIs(view, namespace[name])
        installed = {name: namespace[name] for name, _ in HANDLERS}
        patterns = namespace["COMMERCIAL_URLPATTERNS"]
        patch_commercial(namespace)
        self.assertIs(namespace["COMMERCIAL_URLPATTERNS"], patterns)
        for name, original in installed.items():
            self.assertIs(namespace[name], original)

    def test_rejected_invoice_does_not_record_created_event(self):
        namespace = _namespace()
        patch_commercial(namespace)
        request = RequestFactory().post("/commerce/trx-easy/start/72/")
        request._dont_enforce_csrf_checks = True
        with patch("services.mpw_trx_guest_commerce._dispatch",
                   return_value=HttpResponse(status=400)), \
             patch("services.mpw_trx_guest_commerce._record_funnel_event_best_effort") as event:
            response = namespace["start_order"](request, product_id=72)
        self.assertEqual(response.status_code, 400)
        event.assert_not_called()

    def test_accepted_invoice_records_created_event(self):
        namespace = _namespace()
        patch_commercial(namespace)
        request = RequestFactory().post("/commerce/trx-easy/start/72/")
        request._dont_enforce_csrf_checks = True
        product = MagicMock()
        with patch("services.mpw_trx_guest_commerce._dispatch",
                   return_value=HttpResponse(status=201)), \
             patch("core.models.Product") as model, \
             patch("services.mpw_trx_guest_commerce._record_funnel_event_best_effort") as event:
            model.objects.filter.return_value.first.return_value = product
            response = namespace["start_order"](request, product_id=72)
        self.assertEqual(response.status_code, 201)
        event.assert_called_once_with(request, "invoice_created", product)
