import hashlib
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

try:
    from tron_manual_reconciliation import (
        TronReconciliationError, TrxReceiptCandidate,
        build_review_record, validate_receipt_batch,
        validate_receipt_candidate,
    )
except ModuleNotFoundError:
    from core.tron_manual_reconciliation import (
        TronReconciliationError, TrxReceiptCandidate,
        build_review_record, validate_receipt_batch,
        validate_receipt_candidate,
    )


NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
SCOPE = {"tenant_id": "moj-prop-merchant", "host": "mojplaywin.com", "brand": "moj_prop"}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class TronManualReconciliationTests(unittest.TestCase):
    def candidate(self, **changes):
        values = {
            "receipt_id": "receipt-001",
            "tenant_id": "moj-prop-merchant",
            "host": "mojplaywin.com",
            "brand": "moj_prop",
            "invoice_id": "invoice-001",
            "tx_id": digest("tx-001"),
            "network": "tron-mainnet",
            "asset": "TRX",
            "amount_sun": 30_000_000,
            "confirmations": 20,
            "required_confirmations": 19,
            "observed_at": "2026-11-15T11:59:00Z",
            "to_address_digest": digest("merchant-address"),
            "provider_reference_digest": digest("provider-reference"),
        }
        values.update(changes)
        return TrxReceiptCandidate(**values)

    def test_valid_receipt_is_reviewable_but_not_settled(self):
        record = build_review_record(self.candidate(), SCOPE, now=NOW)
        self.assertTrue(record["reviewable"])
        self.assertEqual(record["state"], "observed_pending_independent_settlement")
        self.assertFalse(record["settled"])
        self.assertFalse(record["entitlement_granted"])
        self.assertFalse(record["revenue_collected"])

    def test_insufficient_confirmations_stays_pending(self):
        record = build_review_record(
            self.candidate(confirmations=2), SCOPE, now=NOW
        )
        self.assertFalse(record["reviewable"])
        self.assertFalse(record["settled"])

    def test_scope_is_exactly_tenant_isolated(self):
        with self.assertRaisesRegex(TronReconciliationError, "scope_mismatch"):
            validate_receipt_candidate(
                self.candidate(tenant_id="other-tenant"), SCOPE, now=NOW
            )
        with self.assertRaisesRegex(TronReconciliationError, "scope_mismatch"):
            validate_receipt_candidate(
                self.candidate(brand="other_brand"), SCOPE, now=NOW
            )

    def test_only_canonical_tron_asset_is_accepted(self):
        with self.assertRaisesRegex(TronReconciliationError, "canonical_tron_asset"):
            validate_receipt_candidate(
                self.candidate(network="tron-testnet"), SCOPE, now=NOW
            )
        with self.assertRaisesRegex(TronReconciliationError, "canonical_tron_asset"):
            validate_receipt_candidate(
                self.candidate(asset="USDT"), SCOPE, now=NOW
            )

    def test_amount_must_be_integer_sun_not_float_or_bool(self):
        for value in (30.5, True, 0, -1):
            with self.subTest(value=value), self.assertRaisesRegex(
                TronReconciliationError, "amount_sun"
            ):
                validate_receipt_candidate(
                    self.candidate(amount_sun=value), SCOPE, now=NOW
                )

    def test_confirmation_types_are_strict(self):
        for value in (True, -1, 1.5):
            with self.subTest(value=value), self.assertRaisesRegex(
                TronReconciliationError, "confirmations"
            ):
                validate_receipt_candidate(
                    self.candidate(confirmations=value), SCOPE, now=NOW
                )

    def test_future_observation_is_rejected(self):
        with self.assertRaisesRegex(TronReconciliationError, "observed_in_future"):
            validate_receipt_candidate(
                self.candidate(observed_at="2026-11-15T12:01:00Z"),
                SCOPE, now=NOW
            )

    def test_digests_hide_raw_address_and_provider_reference(self):
        record = build_review_record(self.candidate(), SCOPE, now=NOW)
        self.assertNotIn("merchant-address", str(record))
        self.assertNotIn("provider-reference", str(record))
        self.assertEqual(len(record["to_address_digest"]) if "to_address_digest" in record else 64, 64)

    def test_batch_rejects_duplicate_transaction(self):
        with self.assertRaisesRegex(TronReconciliationError, "duplicate_transaction_id"):
            validate_receipt_batch([
                self.candidate(),
                self.candidate(receipt_id="receipt-002"),
            ])

    def test_batch_rejects_duplicate_receipt(self):
        second = self.candidate(tx_id=digest("tx-002"))
        with self.assertRaisesRegex(TronReconciliationError, "duplicate_receipt_id"):
            validate_receipt_batch([self.candidate(), second])

    def test_batch_accepts_distinct_receipts_and_transactions(self):
        result = validate_receipt_batch([
            self.candidate(),
            self.candidate(receipt_id="receipt-002", tx_id=digest("tx-002")),
        ])
        self.assertEqual(len(result), 2)

    def test_required_confirmation_count_must_be_positive(self):
        with self.assertRaisesRegex(TronReconciliationError, "required_confirmations"):
            validate_receipt_candidate(
                self.candidate(required_confirmations=0), SCOPE, now=NOW
            )

    def test_no_raw_customer_or_wallet_fields_are_required(self):
        candidate = self.candidate()
        self.assertFalse(hasattr(candidate, "to_address"))
        self.assertFalse(hasattr(candidate, "customer_email"))

    def test_exact_scope_shape_is_required(self):
        with self.assertRaisesRegex(TronReconciliationError, "exact_tenant_scope"):
            validate_receipt_candidate(
                self.candidate(), {"tenant_id": "moj-prop-merchant"}, now=NOW
            )


    def test_literal_fake_transaction_id_rejected(self):
        with self.assertRaisesRegex(TronReconciliationError, "tx_id_invalid"):
            validate_receipt_candidate(self.candidate(tx_id="tx-001"), SCOPE, now=NOW)

    def test_receipt_amount_must_fit_canonical_sun_ledger(self):
        with self.assertRaisesRegex(TronReconciliationError, "amount_sun"):
            validate_receipt_candidate(
                self.candidate(amount_sun=10**15 + 1), SCOPE, now=NOW
            )

    def test_confirmation_target_has_reasonable_bound(self):
        with self.assertRaisesRegex(TronReconciliationError, "required_confirmations"):
            validate_receipt_candidate(
                self.candidate(required_confirmations=10001), SCOPE, now=NOW
            )

    def test_all_zero_provider_proof_digest_rejected(self):
        with self.assertRaisesRegex(TronReconciliationError, "provider_reference_digest"):
            validate_receipt_candidate(
                self.candidate(provider_reference_digest="0" * 64), SCOPE, now=NOW
            )

    def test_clock_object_is_validated_before_comparison(self):
        with self.assertRaisesRegex(TronReconciliationError, "reconciliation_clock"):
            validate_receipt_candidate(self.candidate(), SCOPE, now=object())

    def test_batch_malformed_item_has_contract_error(self):
        with self.assertRaisesRegex(TronReconciliationError, "receipt_candidate_required"):
            validate_receipt_batch([None])

    def test_batch_size_bounded_to_protect_reconciler(self):
        with self.assertRaisesRegex(TronReconciliationError, "receipt_batch_too_large"):
            validate_receipt_batch([self.candidate()] * 501)

    def test_review_preserves_correlatable_digests_without_settlement(self):
        candidate = self.candidate()
        record = build_review_record(candidate, SCOPE, now=NOW)
        self.assertEqual(record["observed_at"], candidate.observed_at)
        self.assertEqual(record["to_address_digest"], candidate.to_address_digest)
        self.assertEqual(
            record["provider_reference_digest"], candidate.provider_reference_digest
        )
        self.assertIs(record["revenue_collected"], False)



if __name__ == "__main__":
    unittest.main()
