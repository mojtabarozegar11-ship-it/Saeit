"""Fail-safe optional funnel analytics for MojPlayWin guest checkout.

All tests use synthetic request/response objects; no invoice, buyer record,
TRX transfer, mail, download entitlement, or production database is touched.
"""

from unittest.mock import patch, sentinel

from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase

from services.mpw_trx_guest_commerce import (
    _record_optional_funnel_event,
    patch_commercial,
)


class GuestCheckoutOptionalFunnelTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post(
            "/commerce/trx-easy/start/72/", secure=True, HTTP_HOST="mojplaywin.com"
        )
        self.request._dont_enforce_csrf_checks = True

    def test_healthy_recorder_receives_original_event(self):
        with patch("core.commerce_funnel.record_funnel_event") as recorder:
            _record_optional_funnel_event(
                self.request, "begin_checkout", product=sentinel.product
            )
        recorder.assert_called_once_with(
            self.request, "begin_checkout", sentinel.product
        )

    def test_missing_optional_module_cannot_block_checkout(self):
        with patch.dict("sys.modules", {"core.commerce_funnel": None}):
            with self.assertLogs(
                "services.mpw_trx_guest_commerce", level="WARNING"
            ) as logs:
                _record_optional_funnel_event(
                    self.request, "begin_checkout", product=sentinel.product
                )
        self.assertIn("ModuleNotFoundError", "\n".join(logs.output))

    def test_telemetry_product_lookup_error_is_redacted(self):
        secret = "private-buyer@example.invalid"
        with patch(
            "core.models.Product.objects.filter", side_effect=ValueError(secret)
        ), self.assertLogs(
            "services.mpw_trx_guest_commerce", level="WARNING"
        ) as logs:
            _record_optional_funnel_event(
                self.request, "invoice_created", product_id=72
            )
        self.assertNotIn(secret, "\n".join(logs.output))
        self.assertIn("ValueError", "\n".join(logs.output))

    def test_post_invoice_response_survives_optional_lookup_failure(self):
        response = HttpResponseRedirect("/commerce/trx-easy/invoice/9/")
        namespace = {
            "_start_order": lambda request, *args, **kwargs: response,
            "_show_invoice": lambda request, *args, **kwargs: response,
            "_invoice_status": lambda request, *args, **kwargs: response,
            "_reconcile_invoice": lambda request, *args, **kwargs: response,
            "_download_paid": lambda request, *args, **kwargs: response,
        }
        patch_commercial(namespace)
        with patch(
            "services.mpw_trx_guest_commerce._dispatch", return_value=response
        ) as dispatch, patch(
            "core.models.Product.objects.filter",
            side_effect=ValueError("private-invoice-data"),
        ), self.assertLogs(
            "services.mpw_trx_guest_commerce", level="WARNING"
        ) as logs:
            result = namespace["start_order"](self.request, product_id=72)

        dispatch.assert_called_once()
        self.assertIs(result, response)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/commerce/trx-easy/invoice/9/")
        self.assertNotIn("private-invoice-data", "\n".join(logs.output))
