"""Invoice creation telemetry must count only the committed invoice redirect.

No DB, network, buyer records, payment, signing key or real purchase.
"""
from django.http import HttpResponse, HttpResponseRedirect
from django.test import SimpleTestCase
from services.mpw_trx_guest_commerce import _confirmed_new_invoice_redirect


class GuestInvoiceSuccessTelemetryTests(SimpleTestCase):
    def test_exact_committed_invoice_redirect_is_countable(self):
        for status in (302, 303):
            with self.subTest(status=status):
                resp = HttpResponseRedirect("/commerce/trx-easy/invoice/5678/")
                resp.status_code = status
                self.assertTrue(_confirmed_new_invoice_redirect(resp))

    def test_login_redirect_never_means_order_created(self):
        for url in ("/accounts/login/?next=/commerce/trx-easy/start/72/",
                    "/login/", "https://malicious.example/invoice/5678/",
                    "/commerce/trx-easy/invoice/0/",
                    "/commerce/trx-easy/invoice/5678/?other=1",
                    "/commerce/trx-easy/invoice/5678/anything"):
            with self.subTest(location=url):
                self.assertFalse(_confirmed_new_invoice_redirect(HttpResponseRedirect(url)))

    def test_200_render_or_errors_are_not_invoice_creation(self):
        for code in (200, 201, 202, 204, 301, 400, 403, 404, 429, 500):
            with self.subTest(code=code):
                response = HttpResponse(status=code)
                response["Location"] = "/commerce/trx-easy/invoice/5678/"
                self.assertFalse(_confirmed_new_invoice_redirect(response))

    def test_view_records_after_verified_return_not_on_generic_http_success(self):
        import inspect
        from services.mpw_trx_guest_commerce import patch_commercial
        src = inspect.getsource(patch_commercial)
        self.assertIn("if _confirmed_new_invoice_redirect(response):", src)
        self.assertNotIn("if 200 <= status_code < 300:", src)
        self.assertIn('request, "invoice_created", product', src)


if __name__ == "__main__":
    import unittest
    unittest.main()
