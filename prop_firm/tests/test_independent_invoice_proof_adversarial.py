"""Adversarial regression for the independent TRON proof guard; no live RPC."""
import unittest
from dataclasses import replace

from prop_firm.independent_invoice_proof_gate import (
    FinalizedTransferProof, SettlementProofRejected, require_matching_finalized_proofs,
)
from prop_firm.invoice_price_snapshot_guard import InvoicePriceSnapshot
from prop_firm.versioned_invoice_pricing import FIRST_FEE_SUN, PRICE_VERSION, PurchaseClass


class IndependentProofAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = InvoicePriceSnapshot(
            sku="mojprop-starter30", purchase_class=PurchaseClass.FIRST.value,
            price_version=PRICE_VERSION, amount_sun=FIRST_FEE_SUN,
            currency="TRX", network="tron-mainnet",
        )
        self.txid = "a" * 64
        self.sender = "41" + "1" * 40
        self.receiver = "41" + "2" * 40
        self.a = FinalizedTransferProof("publicnode", "operator-a", self.txid,
            "tron-mainnet", self.sender, self.receiver, FIRST_FEE_SUN, True, True)
        self.b = replace(self.a, provider_id="trongrid", operator_id="operator-b")

    def verify(self, a=None, b=None):
        return require_matching_finalized_proofs(
            snapshot=self.snapshot, expected_txid=self.txid,
            expected_recipient_hex41=self.receiver, expected_sender_hex41=self.sender,
            first=self.a if a is None else a, second=self.b if b is None else b,
        )

    def test_valid_structured_proofs(self):
        self.assertEqual(self.verify(), self.txid)

    def test_provider_case_and_whitespace_alias_rejected(self):
        with self.assertRaises(SettlementProofRejected):
            self.verify(b=replace(self.b, provider_id=" PUBLICNODE "))

    def test_operator_case_and_whitespace_alias_rejected(self):
        with self.assertRaises(SettlementProofRejected):
            self.verify(b=replace(self.b, operator_id=" OPERATOR-A "))

    def test_blank_provider_rejected(self):
        with self.assertRaises(SettlementProofRejected):
            self.verify(b=replace(self.b, provider_id="  "))

    def test_null_txid_rejected_as_domain_error(self):
        with self.assertRaises(SettlementProofRejected):
            self.verify(b=replace(self.b, txid=None))

    def test_null_network_rejected_as_domain_error(self):
        with self.assertRaises(SettlementProofRejected):
            self.verify(b=replace(self.b, network=None))

    def test_wrong_amount_rejected(self):
        with self.assertRaises(SettlementProofRejected):
            self.verify(b=replace(self.b, amount_sun=FIRST_FEE_SUN - 1))

    def test_not_final_rejected(self):
        with self.assertRaises(SettlementProofRejected):
            self.verify(b=replace(self.b, solidified=False))


if __name__ == "__main__":
    unittest.main()
