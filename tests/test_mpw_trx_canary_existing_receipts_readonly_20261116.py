"""Read-only TRX canary diagnosis never equates a source flag to real revenue."""
from pathlib import Path
import unittest

from scripts.mpw_trx_canary_existing_receipts_readonly_20261116 import (
    analyze_gate_source, classify_payment_evidence,
)

ROOT = Path(__file__).resolve().parents[1]


class InvoiceGateReadOnlyTests(unittest.TestCase):
    def test_source_gate_references_are_not_assumed(self):
        observed = analyze_gate_source(
            'if settings.MPW_WALLETLESS_TRX_PUBLIC_ENABLED is not True: raise ValueError'
        )
        self.assertTrue(observed["source_available"])
        self.assertTrue(observed["direct_public_reference"])
        self.assertFalse(observed["direct_canary_reference"])

    def test_explicit_canary_source_reference_detected(self):
        observed = analyze_gate_source(
            'if settings.MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED is not True: raise ValueError'
        )
        self.assertTrue(observed["direct_canary_reference"])
        self.assertFalse(observed["direct_public_reference"])

    def test_missing_source_does_not_count_as_contract(self):
        self.assertFalse(analyze_gate_source("")["source_available"])
        self.assertFalse(analyze_gate_source("")["source_hash_present"])

    def test_no_payment_evidence_never_claims_revenue(self):
        result = classify_payment_evidence(
            paid_intent_present=False,
            stored_receipt_found=False,
            recorded_delivery_present=False,
            scope_exhaustive=True,
        )
        self.assertFalse(result["paid_intent_present"])
        self.assertFalse(result["stored_verified_receipt_contract_present"])
        self.assertFalse(result["independent_current_chain_finality_checked"])
        self.assertFalse(result["revenue_amount_assessed"])

    def test_verified_stored_receipt_still_not_live_chain_or_buyer_delivery(self):
        result = classify_payment_evidence(
            paid_intent_present=True,
            stored_receipt_found=True,
            recorded_delivery_present=True,
            scope_exhaustive=True,
        )
        self.assertTrue(result["stored_verified_receipt_contract_present"])
        self.assertFalse(result["independent_current_chain_finality_checked"])
        self.assertFalse(result["specific_customer_receipt_and_delivery_matched"])
        self.assertFalse(result["new_customer_payments_created"])

    def test_truthy_strings_not_passed_as_verified_booleans(self):
        result = classify_payment_evidence(
            paid_intent_present="yes",
            stored_receipt_found=1,
            recorded_delivery_present="True",
            scope_exhaustive=False,
        )
        self.assertFalse(result["paid_intent_present"])
        self.assertFalse(result["stored_verified_receipt_contract_present"])
        self.assertFalse(result["any_delivery_event_recorded_unattributed"])
        self.assertFalse(result["paid_receipt_review_exhaustive"])

    def test_live_script_no_payment_mutations_or_wallet_secrets(self):
        script = (ROOT / "scripts/mpw_trx_canary_existing_receipts_readonly_20261116.py").read_text()
        for banned in (
            "requests.post(", "broadcasttransaction", "sendrawtransaction",
            ".save(", ".delete(", "objects.create(", "objects.update(", "objects.delete(",
            ".env", "private_key", "mnemonic", "seed_phrase",
            "print(intent)", "print(order)", "print(ADDRESS)",
        ):
            with self.subTest(token=banned):
                self.assertNotIn(banned, script)
        self.assertIn('MAX_REVIEW = 25', script)
        self.assertIn('from core.crown_tron_receipts import verified_walletless_credit', script)
        self.assertIn('paid.select_related("order").order_by("pk")[:MAX_REVIEW]', script)
        self.assertIn('no_host_changes_or_financial_writes', script)

    def test_live_runner_workflow_cannot_send_payment_or_change_cpanel(self):
        wf = (ROOT / ".github/workflows/mpw-trx-safe-flags-evidence-20261115.yml").read_text()
        self.assertIn("scripts/mpw_trx_canary_existing_receipts_readonly_20261116.py", wf)
        self.assertIn("tests.test_mpw_trx_canary_existing_receipts_readonly_20261116", wf)
        self.assertIn("MPW_TRX_CANARY_RECEIPT_READONLY=", wf)
        self.assertIn("persist-credentials: false", wf)
        self.assertIn("permissions: {contents: read}", wf)
        self.assertIn("pull_request:", wf)
        self.assertNotIn("workflow_dispatch:", wf)
        self.assertNotIn("  push:", wf)
        self.assertNotIn("curl -X POST", wf)


if __name__ == "__main__":
    unittest.main()
