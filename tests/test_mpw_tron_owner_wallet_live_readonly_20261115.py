"""No customer data or live payment may leak from recipient compatibility audit."""
from types import SimpleNamespace
import unittest

from scripts.mpw_tron_owner_wallet_live_readonly_20261115 import (
    OWNER_QR, safe_report,
)


class OwnerReceiverHostReadonlyTests(unittest.TestCase):
    def setUp(self):
        self.flags = SimpleNamespace(
            MPW_COMMERCE_INVOICING_ENABLED=True,
            MPW_COMMERCE_REAL_RPC_ENABLED=True,
            MPW_COMMERCE_SETTLEMENT_ENABLED=False,
            MPW_TRX_MERCHANT_BINDINGS={
                "mojplaywin.com": {
                    "domain": "mojplaywin.com",
                    "merchant_id": "mojplaywin-store",
                    "network": "tron-mainnet",
                    "recipient": OWNER_QR,
                    "enabled": False,
                }
            },
        )

    def test_matching_native_trx_receiver_readonly(self):
        result = safe_report(self.flags, ("tron-mainnet", OWNER_QR, 6))
        self.assertTrue(result["owner_qr_receiver_match"])
        self.assertTrue(result["effective_receiver_native_mainnet"])
        self.assertTrue(result["host_registry_matches_qr"])
        self.assertFalse(result["host_registry_enabled"])
        self.assertFalse(result["settlement_enabled"])
        self.assertFalse(result["live_sale_verified"])
        self.assertFalse(result["payment_finality_checked"])
        self.assertTrue(result["read_only"])

    def test_mismatched_receiver_does_not_print_unknown_wallet(self):
        other = "TA4Wt1DUCqz6YegbnsmqsWC5uUfbdBqPxm"
        result = safe_report(self.flags, ("tron-mainnet", other, 6))
        self.assertFalse(result["owner_qr_receiver_match"])
        self.assertNotIn(other, str(result))
        self.assertNotIn(OWNER_QR, str(result))

    def test_missing_module_and_blank_configuration_fail_closed(self):
        missing = safe_report(SimpleNamespace(), None)
        self.assertFalse(missing["owner_qr_receiver_match"])
        self.assertFalse(missing["receiver_tuple_present"])
        self.assertFalse(missing["host_registry_enabled"])
        self.assertFalse(missing["commercial_invoicing_enabled"])

    def test_wrong_chain_units_never_count_as_matching_native_payment(self):
        for value in (("shasta", OWNER_QR, 6),
                      ("tron-mainnet", OWNER_QR, 18),
                      ("tron-mainnet", OWNER_QR, "6")):
            with self.subTest(value=value):
                result = safe_report(self.flags, value)
                self.assertFalse(result["effective_receiver_native_mainnet"])
                self.assertFalse(result["payment_finality_checked"])

    def test_user_attestation_is_not_a_signature_or_money(self):
        r = safe_report(self.flags, ("tron-mainnet", OWNER_QR, 6))
        self.assertEqual(r["owned_wallet"], "user_attested_not_independently_signed")
        self.assertNotIn("revenue_received", r)
        self.assertFalse(r["customer_delivery_checked"])


if __name__ == "__main__":
    unittest.main()
