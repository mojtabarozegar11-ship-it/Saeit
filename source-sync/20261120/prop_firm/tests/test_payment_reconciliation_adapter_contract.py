"""Static contract tests for the private payment reconciliation bridge."""
from pathlib import Path
import unittest


class PaymentReconciliationAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.source = (cls.root / "payment_reconciliation_adapter.py").read_text(
            encoding="utf-8"
        )

    def test_source_and_target_aliases_are_explicit(self):
        source = self.source
        for marker in (
            "MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS",
            "source_alias == MOJPROP_DB_ALIAS",
            "PropPlan1Receipt.objects.using(source_alias)",
            "PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)",
            "PropSimulationInvoiceOwner.objects.using(MOJPROP_DB_ALIAS)",
            "select_related",
            "select_for_update",
            "transaction.atomic(using=MOJPROP_DB_ALIAS)",
        ):
            self.assertIn(marker, source)

    def test_only_independently_attested_settlement_can_bind_ownership(self):
        source = self.source
        for marker in (
            "trusted_reconciler_attestation",
            "ledger.tx_hash != attestation.tx_hash",
            "ledger.evidence_digest != attestation.evidence_digest",
            "invoice.status != \"paid\"",
            '"settlement_verified": True',
            "PropSimulationInvoiceOwner",
        ):
            self.assertIn(marker, source)

    def test_no_public_or_cash_side_effects(self):
        source = self.source
        for forbidden in (
            "request",
            "send_mail",
            "broadcast",
            "payout",
            "create_account",
            "MPW_MOJPROP_PLAN1_ROUTE_ENABLED = True",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
