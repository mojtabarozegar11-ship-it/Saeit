"""MojPlayWin fiat->native TRX: no customer purchase or payout without proof."""
import unittest

from mpw_fiat_to_trx_20261020.provider_adapter import (
    merchant_release_report, payment_claim_matches,
    payout_is_independently_verified,
)


class MerchantFiatGateTests(unittest.TestCase):
    def test_gate_defaults_closed_and_does_not_leak_values(self):
        env = {"NOWPAYMENTS_API_KEY": "private-key",
               "NOWPAYMENTS_IPN_SECRET": "private-ipn"}
        report = merchant_release_report(env)
        self.assertFalse(report["release_permitted"])
        self.assertIn("MPW_FIAT_BACKUP_RESTORE_VERIFIED", report["missing"])
        self.assertNotIn("private-key", str(report))
        self.assertNotIn("private-ipn", str(report))

    def test_no_false_ready_if_any_independent_gate_is_missing(self):
        env = {
            key: "1" for key in (
                "MPW_FIAT_ONRAMP_APPROVED",
                "MPW_FIAT_TRX_PAYOUT_VERIFIED",
                "MPW_FIAT_IPN_PUBLIC_VERIFIED",
                "MPW_FIAT_PRIVATE_DELIVERY_VERIFIED",
                "MPW_FIAT_TENANT_ISOLATION_VERIFIED",
                "MPW_FIAT_BACKUP_RESTORE_VERIFIED",
                "MPW_FIAT_LIVE_CANARY_VERIFIED",
            )
        }
        env["NOWPAYMENTS_API_KEY"] = "demo"
        env["NOWPAYMENTS_IPN_SECRET"] = "demo"
        self.assertTrue(merchant_release_report(env)["release_permitted"])
        for key in env:
            reduced = dict(env)
            reduced.pop(key)
            self.assertFalse(merchant_release_report(reduced)["release_permitted"], key)

    def test_finished_invoice_not_equal_to_payout(self):
        event = {
            "payment_id": 123,
            "invoice_id": 789,
            "order_id": "MPWF-ABCD123456789",
            "price_amount": "7.50",
            "price_currency": "usd",
            "payment_status": "finished",
            "outcome_amount": "18.5",
            "outcome_currency": "trx",
        }
        args = dict(order_id=event["order_id"], invoice_id=789, price_usd="7.50")
        self.assertTrue(payment_claim_matches(event, **args))
        for key, value in (
            ("payment_status", "waiting"),
            ("price_amount", "7.49"),
            ("price_currency", "eur"),
            ("outcome_currency", "usdttrc20"),
            ("outcome_amount", "0"),
            ("order_id", "wrong"),
            ("invoice_id", 777),
            ("payment_id", None),
        ):
            changed = dict(event)
            changed[key] = value
            self.assertFalse(payment_claim_matches(changed, **args), key)
        self.assertFalse(payment_claim_matches({"price_amount": "nan"}, **args))
        self.assertFalse(payment_claim_matches({"price_amount": "Infinity"}, **args))

    def test_download_requires_trusted_native_payout_evidence(self):
        args = dict(
            payment_matches=True,
            merchant_receipt_verified=True,
            chain_is_tron_mainnet=True,
            wallet_matches=True,
            tx_unique=True,
            order_is_unfulfilled=True,
        )
        self.assertTrue(payout_is_independently_verified(**args))
        for key in args:
            changed = dict(args)
            changed[key] = False
            self.assertFalse(payout_is_independently_verified(**changed), key)


    def test_invoice_creation_will_not_open_provider_before_complete_release_gates(self):
        from mpw_fiat_to_trx_20261020.provider_adapter import create_invoice, MerchantNotReady
        partial = {
            "MPW_FIAT_ONRAMP_APPROVED": "1",
            "MPW_FIAT_TRX_PAYOUT_VERIFIED": "1",
            "NOWPAYMENTS_API_KEY": "redacted",
            "NOWPAYMENTS_IPN_SECRET": "redacted",
        }
        opened = []
        def fake_open(*args, **kwargs):
            opened.append(True)
            raise AssertionError("The provider must not be contacted")
        with self.assertRaises(MerchantNotReady):
            create_invoice(
                "MPWF-ABCDEF12345678", "7.50", "Chess",
                "https://mojplaywin.com/ipn/",
                "https://mojplaywin.com/ok/",
                "https://mojplaywin.com/cancel/",
                env=partial, opener=fake_open)
        self.assertEqual(opened, [])

if __name__ == "__main__":
    unittest.main()
