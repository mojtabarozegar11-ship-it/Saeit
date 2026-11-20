"""Offline checkout gate regression coverage; no customer, DB or TRON access."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings


OPEN = {
    "MPW_MOJPROP_DB_ALIAS_ENABLED": True,
    "MPW_MOJPROP_DEPLOYMENT_ENV": "production",
    "MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED": True,
    "MPW_MOJPROP_TRX_RELEASE_ENABLED": True,
    "MPW_MOJPROP_TRX_RPC_ATTESTED": True,
}
PATH = "/mojprop-starter30-checkout/"


class Starter30CheckoutBoundaryTests(SimpleTestCase):
    def test_each_verified_release_prerequisite_is_necessary(self):
        from prop_firm.starter30_live import release_is_open
        for key in OPEN:
            with self.subTest(flag=key), override_settings(**{
                **OPEN, key: "staging" if key.endswith("_ENV") else False
            }):
                self.assertFalse(release_is_open())
                response = self.client.get(PATH)
                self.assertContains(response, "Payment is not available")
                self.assertNotContains(response, "Create 30 TRX invoice")
                self.assertNotContains(response, "<form")

    @override_settings(**OPEN)
    def test_open_get_only_presents_disclosure_and_invoice_form(self):
        with patch("prop_firm.starter30_views.issue_invoice") as issue, \
             patch("prop_firm.starter30_views.settle_invoice") as settle:
            response = self.client.get(PATH)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Create 30 TRX invoice")
            self.assertContains(response, "30 TRX")
            self.assertContains(response, "simulated trading")
            self.assertContains(response, "no profit or pass result is guaranteed")
            self.assertContains(response, "Send only after this server issues your unique invoice")
            self.assertContains(response, "csrfmiddlewaretoken")
            issue.assert_not_called()
            settle.assert_not_called()

    def test_closed_post_refuses_before_identity_or_network_access(self):
        from prop_firm.starter30_live import issue_invoice, settle_invoice, Starter30ReleaseClosed
        with override_settings(**{**OPEN, "MPW_MOJPROP_TRX_RELEASE_ENABLED": False}):
            with self.assertRaises(Starter30ReleaseClosed):
                issue_invoice(email="invalid", payer_address="invalid", terms_accepted=True)
            with self.assertRaises(Starter30ReleaseClosed):
                settle_invoice(invoice_ref="invalid", txid="invalid")

    @override_settings(**OPEN)
    def test_public_product_is_not_a_payment_form(self):
        response = self.client.get("/moj-prop/starter-30-trx/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MOJPROP-STARTER30")
        self.assertContains(response, 'href="/mojprop-starter30-checkout/"')
        self.assertContains(response, "No real funded account or customer capital is involved")
        self.assertContains(response, "server-issued 30 TRX invoice")
        self.assertNotContains(response, "<form")
        self.assertNotContains(response, "private key")
        self.assertNotContains(response, "tronweb")
