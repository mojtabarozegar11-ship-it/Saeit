"""DB-free checks for the English checkout's honest free written-terms exit.

GET renders do not issue invoices, send emails, consume network RPC, or write
customer records. Closed release must never advertise a usable paid route.
"""
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from prop_firm.starter30_views import starter30_checkout


class Starter30PreInvoiceInformationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.free_url = (
            "/moj-prop-intake/?format=html&amp;service=blueprint"
            "&amp;package=starter-30-trx"
        )

    def test_open_checkout_offers_zero_cost_terms_and_rules(self):
        request = self.factory.get("/mojprop-starter30-checkout/")
        with (
            patch("prop_firm.starter30_live.release_is_open", return_value=True),
            patch("prop_firm.starter30_views.verify_pre_invoice_configuration"),
            patch("prop_firm.starter30_views._record_funnel_event"),
            patch("prop_firm.starter30_views._email_forms",
                  return_value="<p>EMAIL-VERIFICATION-FORM</p>"),
        ):
            response = starter30_checkout(request)
        html = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.free_url, html)
        self.assertIn("/moj-prop/rules/", html)
        self.assertIn("/moj-prop/payment/", html)
        self.assertIn("does not issue an invoice, collect TRX, or open an account", html)
        self.assertIn("EMAIL-VERIFICATION-FORM", html)

    def test_closed_checkout_retains_free_information_route_but_no_payment_form(self):
        request = self.factory.get("/mojprop-starter30-checkout/")
        with patch("prop_firm.starter30_live.release_is_open", return_value=False):
            response = starter30_checkout(request)
        html = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No transfer should be sent", html)
        self.assertIn(self.free_url, html)
        self.assertNotIn("<form ", html)
        self.assertNotIn("Create 30 TRX invoice", html)

    def test_invalid_post_explains_error_and_offers_free_information(self):
        request = self.factory.post(
            "/mojprop-starter30-checkout/", data={"action": "unsupported"}
        )
        with patch("prop_firm.starter30_views._email_forms",
                   return_value="<p>RECOVERY-EMAIL-FORM</p>"):
            response = starter30_checkout(request)
        html = response.content.decode("utf-8")
        self.assertIn("Payment not credited", html)
        self.assertIn(self.free_url, html)
        self.assertIn("RECOVERY-EMAIL-FORM", html)
        self.assertNotIn("Invoice issued", html)

    def test_external_tracking_data_not_reflected_in_constant_links(self):
        request = self.factory.get(
            "/mojprop-starter30-checkout/?utm_source=%3Csvg%20onload%3Devil%3E"
        )
        with patch("prop_firm.starter30_live.release_is_open", return_value=False):
            html = starter30_checkout(request).content.decode("utf-8")
        self.assertIn(self.free_url, html)
        self.assertNotIn("<svg", html)
        self.assertNotIn("onload=evil", html)
