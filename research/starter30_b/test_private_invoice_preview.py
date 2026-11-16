"""Offline contract preview regression tests; never connect to live payments."""
from datetime import datetime, timedelta, timezone
import unittest

from research.starter30_b.private_invoice_preview import prepare_private_invoice


class PrivateInvoicePreviewTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.args = dict(
            order_ref="STARTER30_ORDER_00001", buyer_reference="buyer-opaque-id",
            consent_evidence="opt-in-record-v1", contract_version="educational-10-session-v1",
            buyer_signature="buyer-signed-proof", seller_signature="seller-signed-proof",
            issued_at=self.now, expires_at=self.now + timedelta(days=1),
            verified_merchant=True, verified_buyer=True,
            consent_confirmed=True, signatures_verified=True,
        )

    def test_fixed_native_price_and_non_payable(self):
        p = prepare_private_invoice(**self.args)
        self.assertEqual((p.sku, p.network, p.amount_sun, p.status),
                         ("MOJPROP-STARTER30", "tron-mainnet", 30_000_000, "draft_non_payable"))
        self.assertNotIn(self.args["buyer_reference"], repr(p))

    def test_each_gate_required(self):
        for gate in ("verified_merchant", "verified_buyer", "consent_confirmed", "signatures_verified"):
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                prepare_private_invoice(**(self.args | {gate: False}))

    def test_each_evidence_required(self):
        for key in ("buyer_reference", "consent_evidence", "contract_version",
                    "buyer_signature", "seller_signature"):
            with self.subTest(field=key), self.assertRaises(ValueError):
                prepare_private_invoice(**(self.args | {key: ""}))

    def test_reject_expired_and_overlong(self):
        for delta in (timedelta(0), timedelta(days=-1), timedelta(days=8)):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                prepare_private_invoice(**(self.args | {"expires_at": self.now + delta}))

    def test_reject_naive_timestamp(self):
        with self.assertRaises(ValueError):
            prepare_private_invoice(**(self.args | {"issued_at": self.now.replace(tzinfo=None)}))

    def test_reject_bad_reference(self):
        for value in ("bad", "bad space", "", "x" * 43):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_private_invoice(**(self.args | {"order_ref": value}))


if __name__ == "__main__":
    unittest.main()
