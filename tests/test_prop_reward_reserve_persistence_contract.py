"""Static contract tests for durable reward-reserve persistence."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DurableRewardReserveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = (ROOT / "prop_firm" / "models.py").read_text(encoding="utf-8")
        cls.migration = (
            ROOT / "prop_firm" / "migrations" / "0010_reward_reserve_ledger.py"
        ).read_text(encoding="utf-8")
        cls.persistence = (
            ROOT / "prop_firm" / "reward_reserve_persistence.py"
        ).read_text(encoding="utf-8")

    def test_models_have_durable_allocation_and_commitment(self):
        self.assertIn("class PropRewardReserveAllocation(models.Model)", self.models)
        self.assertIn("class PropRewardCommitment(models.Model)", self.models)
        self.assertIn("committed_reward_sun", self.models)

    def test_migration_depends_on_gateway_contract(self):
        self.assertIn('("prop_firm", "0009_plan1_invoice_gateway")', self.migration)
        self.assertIn("CreateModel", self.migration)
        self.assertIn("PropRewardReserveAllocation", self.migration)
        self.assertIn("PropRewardCommitment", self.migration)

    def test_retry_fee_is_persistable(self):
        self.assertIn('purchase_kind="retry"', self.models)
        self.assertIn("18_000_000", self.models)
        self.assertIn("SUPPORTED_FEES_SUN", self.persistence)

    def test_allocation_is_atomic_and_row_locked(self):
        self.assertIn("@transaction.atomic", self.persistence)
        self.assertIn("select_for_update", self.persistence)

    def test_allocation_requires_paid_invoice(self):
        self.assertIn('invoice.status != "paid"', self.persistence)
        self.assertIn("settlement_receipt_required", self.persistence)
        self.assertIn("trusted_settlement_attestation_required", self.persistence)

    def test_allocation_rejects_duplicates(self):
        self.assertIn("duplicate_reserve_allocation", self.persistence)
        self.assertIn("PropRewardReserveAllocation.objects.filter(invoice=invoice)", self.persistence)

    def test_allocation_uses_eighty_ten_ten_split(self):
        self.assertIn("REWARD_RESERVE_BPS = 8_000", self.persistence)
        self.assertIn("REFUND_RESERVE_BPS = 1_000", self.persistence)
        self.assertIn("OPERATING_BUFFER_BPS = 1_000", self.persistence)

    def test_commitment_is_order_bounded_and_durable(self):
        self.assertIn("reward_exceeds_order_reserve", self.persistence)
        self.assertIn("PropRewardCommitment.objects.create", self.persistence)
        self.assertIn("committed_reward_sun", self.persistence)

    def test_duplicate_commitments_are_rejected(self):
        self.assertIn("duplicate_reward_commitment", self.persistence)
        self.assertIn("commitment_ref=commitment_ref", self.persistence)

    def test_virtual_principal_is_zero(self):
        self.assertIn('"virtual_principal_requirement_sun": 0', self.persistence)

    def test_source_compiles_as_python(self):
        ast.parse(self.models)
        ast.parse(self.migration)
        ast.parse(self.persistence)


if __name__ == "__main__":
    unittest.main()
