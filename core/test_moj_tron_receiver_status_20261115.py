"""The operator status command must never assert a payment from wallet metadata."""
import json
from io import StringIO
from types import SimpleNamespace

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from core.management.commands.moj_tron_receiver_status import receiver_status
from services.mojtaba_tron_owner_receiver import owner_merchant_registry


class OwnerTRXReceiverConfigTests(SimpleTestCase):
    def test_disabled_default_proves_wallet_only_not_checkout(self):
        cfg = SimpleNamespace(
            MPW_TRX_MERCHANT_BINDINGS=owner_merchant_registry(),
            MPW_TRX_INVOICE_RELEASE_VERIFIED=False,
            MPW_TRX_SOLIDITY_RELEASE_VERIFIED=False,
        )
        result = receiver_status(cfg)
        self.assertTrue(result["qr_base58check_valid"])
        self.assertEqual(result["asset"], "TRX")
        self.assertEqual(result["network"], "tron-mainnet")
        self.assertFalse(result["merchant_binding_enabled"])
        self.assertIsNone(result["chain_settlement_verified"])
        self.assertIsNone(result["live_invoice_issuance_verified"])
        self.assertIsNone(result["revenue_received_trx"])

    def test_partial_permissions_do_not_enable_payable_invoice(self):
        for invoice, solidity in ((False, True), (True, False)):
            with self.subTest(invoice=invoice, solidity=solidity):
                cfg = SimpleNamespace(
                    MPW_TRX_MERCHANT_BINDINGS=owner_merchant_registry(
                        invoice_enabled=invoice, finality_enabled=solidity,
                    ),
                    MPW_TRX_INVOICE_RELEASE_VERIFIED=invoice,
                    MPW_TRX_SOLIDITY_RELEASE_VERIFIED=solidity,
                )
                result = receiver_status(cfg)
                self.assertFalse(result["merchant_binding_enabled"])
                self.assertIsNone(result["revenue_received_trx"])

    def test_two_flags_allow_binding_but_not_fabricated_revenue(self):
        cfg = SimpleNamespace(
            MPW_TRX_MERCHANT_BINDINGS=owner_merchant_registry(
                invoice_enabled=True, finality_enabled=True,
            ),
            MPW_TRX_INVOICE_RELEASE_VERIFIED=True,
            MPW_TRX_SOLIDITY_RELEASE_VERIFIED=True,
        )
        result = receiver_status(cfg)
        self.assertTrue(result["merchant_binding_enabled"])
        self.assertIsNone(result["chain_settlement_verified"])
        self.assertIsNone(result["customer_delivery_verified"])
        self.assertIsNone(result["revenue_received_trx"])

    def test_deployed_settings_default_release_flags_are_off(self):
        from django.conf import settings
        # This test uses the repository's own CI settings (no live host).
        self.assertEqual(settings.MPW_TRX_OWNER_RECEIVER[-6:], "2pUi73")
        self.assertEqual(settings.MPW_TRX_MERCHANT_BINDINGS["mojplaywin.com"]["recipient"],
                         settings.MPW_TRX_OWNER_RECEIVER)

    @override_settings(
        MPW_TRX_MERCHANT_BINDINGS=owner_merchant_registry(),
        MPW_TRX_INVOICE_RELEASE_VERIFIED=False,
        MPW_TRX_SOLIDITY_RELEASE_VERIFIED=False,
    )
    def test_management_command_readonly_json_no_full_address_or_credentials(self):
        output = StringIO()
        call_command("moj_tron_receiver_status", stdout=output)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["qr_base58check_valid"])
        self.assertFalse(payload["merchant_binding_enabled"])
        self.assertNotIn("THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73", output.getvalue())
        self.assertNotIn("private_key", output.getvalue())
        self.assertNotIn("password", output.getvalue())
        self.assertNotIn("api_key", output.getvalue())
        self.assertIsNone(payload["revenue_received_trx"])
