"""Contract tests for settlement-to-reward-reserve wiring."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RewardReserveGatewayContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.persistence = (ROOT / "prop_firm" / "plan1_persistence.py").read_text(encoding="utf-8")
        cls.views = (ROOT / "prop_firm" / "plan1_views.py").read_text(encoding="utf-8")

    def test_first_and_retry_fees_are_server_side(self):
        self.assertIn('"first": 30_000_000', self.persistence)
        self.assertIn('"retry": 18_000_000', self.persistence)
        self.assertIn("purchase_kind", self.persistence)

    def test_retry_requires_server_attestation(self):
        self.assertIn("server_retry_eligibility_required", self.persistence)
        self.assertIn("retry_eligibility_verified", self.views)

    def test_invoice_amount_is_not_hardcoded_to_first_price(self):
        self.assertIn("amount_sun=invoice.amount_sun", self.persistence)
        self.assertNotIn("amount_sun=AMOUNT_SUN", self.persistence)

    def test_settlement_creates_receipt_then_reserve(self):
        receipt_index = self.persistence.index("PropPlan1Receipt.objects.create")
        reserve_index = self.persistence.index("allocate_reward_reserve_after_settlement")
        self.assertLess(receipt_index, reserve_index)

    def test_settlement_requires_attestation(self):
        self.assertIn("Independent settlement attestation is required", self.persistence)
        self.assertIn("trusted_reconciler_attestation=True", self.persistence)

    def test_duplicate_tx_is_held(self):
        self.assertIn("Transaction hash already settled", self.persistence)
        self.assertIn("IntegrityError", self.persistence)

    def test_view_returns_purchase_kind(self):
        self.assertIn('"purchase_kind": invoice.purchase_kind', self.views)

    def test_source_compiles(self):
        ast.parse(self.persistence)
        ast.parse(self.views)


if __name__ == "__main__":
    unittest.main()
