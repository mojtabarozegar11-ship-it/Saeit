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
             patch("prop_firm.starter30_views.settle_invoice") as settle, \
             patch("prop_firm.starter30_views.verify_pre_invoice_configuration") as preflight:
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
            preflight.assert_called_once_with()

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

    @override_settings(**OPEN)
    def test_open_flags_but_invalid_rpc_configuration_hide_invoice_form(self):
        from prop_firm.starter30_live import Starter30PaymentRejected
        with patch(
            "prop_firm.starter30_views.verify_pre_invoice_configuration",
            side_effect=Starter30PaymentRejected("RPC config invalid"),
        ):
            response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment is not available")
        self.assertNotContains(response, "Create 30 TRX invoice")
        self.assertNotContains(response, "<form")

    @override_settings(**OPEN)
    def test_invoice_refuses_invalid_provider_configuration_before_db_or_identity_writes(self):
        from services.mpw_trx_walletless_core import PaymentHold
        from prop_firm.starter30_live import (
            Starter30PaymentRejected,
            issue_invoice,
        )
        with patch("prop_firm.starter30_live._provider_pair", side_effect=PaymentHold("misconfigured")), \
             patch("prop_firm.starter30_live.normalize_email") as normalize, \
             patch("prop_firm.starter30_live.PropSimulationIdentity.objects") as identities:
            with self.assertRaisesRegex(Starter30PaymentRejected, "no invoice"):
                issue_invoice(
                    email="buyer@example.com",
                    payer_address="not-validated-yet",
                    terms_accepted=True,
                )
            normalize.assert_not_called()
            identities.assert_not_called()

    @override_settings(**OPEN)
    def test_settlement_configuration_failure_is_controlled_buyer_rejection(self):
        from services.mpw_trx_walletless_core import PaymentHold
        from prop_firm.starter30_live import (
            Starter30PaymentRejected,
            settle_invoice,
        )
        with patch("prop_firm.starter30_live._provider_pair", side_effect=PaymentHold("bad config")), \
             patch("prop_firm.starter30_live.PropSimulationPayment.objects") as payments:
            with self.assertRaisesRegex(Starter30PaymentRejected, "configuration"):
                settle_invoice(invoice_ref="unused", txid="0" * 64)
            payments.assert_not_called()
