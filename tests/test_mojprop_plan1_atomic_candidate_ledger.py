"""Offline regression checks for candidate-only global replay ledger."""
import sqlite3
import unittest
from services.mojprop_plan1_atomic_candidate_ledger import (
    REQUIRED, initialize, reserve_candidate, SettlementBlocked,
)

def fixtures():
    ref = "MOJPROP01-ABCDEFGHIJKL"
    digest = "a" * 64
    candidate = dict(schema="mojprop.plan1.tron.match.v1",
        candidate_matches_persisted_order=True, buyer_entitlement_granted=False,
        revenue_booked=False, network="tron-mainnet", product="MOJ-PROP-01",
        amount_sun=30_000_000, contract_version="2026-11-15/v1.2",
        order_ref=ref, precontract_sha256=digest, txid="b" * 64)
    order = dict(order_ref=ref, product="MOJ-PROP-01", network="tron-mainnet",
        contract_version="2026-11-15/v1.2", precontract_sha256=digest,
        amount_sun=30_000_000, authenticated=True, payable_release=True)
    return candidate, order, dict.fromkeys(REQUIRED, True)

class CandidateLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        initialize(self.db)
        self.c, self.o, self.g = fixtures()

    def tearDown(self):
        self.db.close()

    def reserve(self):
        return reserve_candidate(self.db, candidate=self.c, order=self.o, gates=self.g)

    def test_reservation_never_credits(self):
        result = self.reserve()
        self.assertEqual(result["status"], "CANDIDATE_RESERVED_NOT_SETTLED")
        for field in ("checkout_enabled", "receipt_signed", "revenue_booked",
                      "challenge_activated", "refund_executed"):
            self.assertIs(result[field], False)

    def test_global_txid_replay_rejected(self):
        self.reserve()
        self.o["order_ref"] = self.c["order_ref"] = "MOJPROP01-XXXXXXXXXXXX"
        with self.assertRaises(SettlementBlocked):
            self.reserve()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM global_tron_tx_claims").fetchone()[0], 1)

    def test_one_order_cannot_claim_two_txids(self):
        self.reserve()
        self.c["txid"] = "c" * 64
        with self.assertRaises(SettlementBlocked):
            self.reserve()

    def test_missing_each_gate_rejected(self):
        for gate in REQUIRED:
            self.g[gate] = False
            with self.subTest(gate=gate), self.assertRaises(SettlementBlocked):
                self.reserve()
            self.g[gate] = True

    def test_wrong_product_rejected(self):
        self.c["product"] = "MOJPROP-STARTER30"
        with self.assertRaises(SettlementBlocked):
            self.reserve()

    def test_wrong_network_rejected(self):
        self.c["network"] = "tron-shasta"
        with self.assertRaises(SettlementBlocked):
            self.reserve()

    def test_wrong_amount_rejected(self):
        self.c["amount_sun"] = 29_999_999
        with self.assertRaises(SettlementBlocked):
            self.reserve()

    def test_wrong_terms_rejected(self):
        self.o["precontract_sha256"] = "c" * 64
        with self.assertRaises(SettlementBlocked):
            self.reserve()

    def test_unreleased_order_rejected(self):
        self.o["payable_release"] = False
        with self.assertRaises(SettlementBlocked):
            self.reserve()

    def test_no_ledger_side_effect_on_failure(self):
        self.c["txid"] = "invalid"
        with self.assertRaises(SettlementBlocked):
            self.reserve()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM plan1_settlement_audit").fetchone()[0], 0)

if __name__ == "__main__":
    unittest.main()
