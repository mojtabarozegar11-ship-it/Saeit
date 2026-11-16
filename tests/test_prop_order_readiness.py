"""Regression coverage for the Cycle B pre-order guard (no Django needed)."""
from decimal import Decimal
import unittest

from prop_firm.order_readiness import (
    REQUIRED, SKU, FEE_TRX, TERMS_VERSION, PREPURCHASE_DISCLOSURES,
    assess_plan_one,
)

class ReadinessTests(unittest.TestCase):
    def test_missing_all_twenty_independent_gates(self):
        result = assess_plan_one({})
        self.assertFalse(result.eligible)
        self.assertEqual(result.missing, REQUIRED)
        self.assertEqual(len(REQUIRED), 20)

    def test_each_gate_individually_blocks(self):
        for key in REQUIRED:
            with self.subTest(key=key):
                evidence = dict.fromkeys(REQUIRED, True)
                evidence[key] = False
                self.assertEqual(assess_plan_one(evidence).missing, (key,))

    def test_exact_verified_evidence_only(self):
        for impostor in (1, "true", "yes", [], None):
            with self.subTest(impostor=impostor):
                evidence = dict.fromkeys(REQUIRED, True)
                evidence["buyer_kyc_verified"] = impostor
                self.assertFalse(assess_plan_one(evidence).eligible)

    def test_canonical_contract_price_and_sku(self):
        evidence = dict.fromkeys(REQUIRED, True)
        self.assertTrue(assess_plan_one(evidence).eligible)
        self.assertIn("canonical_sku", assess_plan_one(evidence, sku="Starter30").missing)
        self.assertIn("native_trx_price", assess_plan_one(evidence, fee_trx=Decimal("30.01")).missing)
        self.assertIn("native_trx_price", assess_plan_one(evidence, fee_trx=30).missing)
        self.assertIn("versioned_contract", assess_plan_one(evidence, contract_version="v1.1").missing)

    def test_prepurchase_copy_contains_critical_disclosures(self):
        copy = " ".join(PREPURCHASE_DISCLOSURES).lower()
        for required in ("simulated", "30 native trx", "28 days", "50 verified",
                         "six verified", "usd 100", "70%", "instagram",
                         "facebook", "refund", "invoice"):
            self.assertIn(required, copy)

if __name__ == "__main__":
    unittest.main()
