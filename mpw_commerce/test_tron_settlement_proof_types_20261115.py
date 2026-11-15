"""Proof validation only: does not settle real orders or transfer TRX."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from mpw_commerce.invoicing import RECEIVERS
from mpw_commerce.settlement import SettlementRejected, _verify_evidence


class TronFinalityProofBoundaryTests(TestCase):
    def setUp(self):
        now = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
        self.receiver = RECEIVERS["TRX"][1]
        self.sender = "TA9pkx4DFxrEw8JZzUtyDrh2uAat1LDuJL"
        self.invoice = SimpleNamespace(
            asset="TRX", network="tron-mainnet", recipient=self.receiver,
            total_usd=Decimal("29.00"), quote_usd_per_asset=Decimal("0.2"),
            quote_source="coinbase", quote_observed_at=now,
            sender_challenge_id="challenge-101",
            sender_signature_verified_at=now, issued_at=now,
            expires_at=now + timedelta(minutes=10), order_id=101,
            expected_sender=self.sender, amount_atomic="145000000",
        )
        self.tx = "a" * 64
        self.proof = dict(
            block_timestamp=now + timedelta(minutes=1),
            finalized=True, order_id=101, network="tron-mainnet",
            tx_hash=self.tx, sender=self.sender, recipient=self.receiver,
            amount_atomic=145000000, backend="tron-mainnet-verified",
        )

    def test_valid_typed_finalized_receipt_is_accepted_as_policy_evidence(self):
        digest, when = _verify_evidence(self.invoice, self.tx, self.proof)
        self.assertEqual(len(digest), 64)
        self.assertEqual(when, self.proof["block_timestamp"])

    def test_tron_sender_letter_case_mismatch_is_not_tolerated(self):
        proof = {**self.proof, "sender": self.sender.replace("A", "a", 1)}
        self.assertNotEqual(proof["sender"], self.sender)
        with self.assertRaises(SettlementRejected):
            _verify_evidence(self.invoice, self.tx, proof)

    def test_tron_recipient_letter_case_mismatch_is_not_tolerated(self):
        proof = {**self.proof, "recipient": self.receiver.replace("H", "h", 1)}
        self.assertNotEqual(proof["recipient"], self.receiver)
        with self.assertRaises(SettlementRejected):
            _verify_evidence(self.invoice, self.tx, proof)

    def test_altered_invoice_destination_is_not_tolerated(self):
        original = self.invoice.recipient
        self.invoice.recipient = original.replace("H", "h", 1)
        with self.assertRaises(SettlementRejected):
            _verify_evidence(self.invoice, self.tx, self.proof)

    def test_malformed_timestamp_types_rejected_without_server_error(self):
        for value in (None, "2026-11-15T10:01:00Z", 1, True, [],
                      datetime(2026, 11, 15, 10, 1)):
            with self.subTest(value=repr(value)), self.assertRaises(SettlementRejected):
                _verify_evidence(self.invoice, self.tx,
                                 {**self.proof, "block_timestamp": value})

    def test_malformed_proof_address_types_rejected_without_server_error(self):
        for key in ("sender", "recipient"):
            for value in (None, 42, True, [], {}):
                with self.subTest(key=key, value=repr(value)), self.assertRaises(SettlementRejected):
                    _verify_evidence(self.invoice, self.tx,
                                     {**self.proof, key: value})

    def test_corrupted_atomic_amount_is_rejected_before_chain_credit(self):
        for bad in ("", "0", "000145000000", "+145000000",
                    "145_000_000", "145000000 ", "1e9", 145000000, None):
            with self.subTest(bad=repr(bad)), self.assertRaises(SettlementRejected):
                self.invoice.amount_atomic = bad
                _verify_evidence(self.invoice, self.tx, self.proof)
        self.invoice.amount_atomic = "145000000"
        self.assertEqual(len(_verify_evidence(self.invoice, self.tx, self.proof)[0]), 64)

    def test_invalid_legacy_price_or_rate_does_not_settle(self):
        for field, invalid in (
            ("total_usd", Decimal("NaN")), ("total_usd", Decimal("Infinity")),
            ("total_usd", Decimal("-1")), ("total_usd", "29.00"),
            ("quote_usd_per_asset", Decimal("NaN")),
            ("quote_usd_per_asset", Decimal("0")),
            ("quote_usd_per_asset", Decimal("Infinity")),
            ("quote_usd_per_asset", 0.2),
        ):
            with self.subTest(field=field, value=repr(invalid)):
                original = getattr(self.invoice, field)
                try:
                    setattr(self.invoice, field, invalid)
                    with self.assertRaises(SettlementRejected):
                        _verify_evidence(self.invoice, self.tx, self.proof)
                finally:
                    setattr(self.invoice, field, original)

    def test_untrusted_dictionary_subclass_cannot_inject_evidence(self):
        class SyntheticProof(dict):
            pass
        with self.assertRaises(SettlementRejected):
            _verify_evidence(self.invoice, self.tx, SyntheticProof(self.proof))

    def test_no_settlement_with_invalid_issuance_clock(self):
        now = self.invoice.issued_at
        invalid = (
            ("quote_observed_at", now + timedelta(seconds=1)),
            ("quote_observed_at", now - timedelta(seconds=91)),
            ("sender_signature_verified_at", now + timedelta(seconds=1)),
            ("sender_signature_verified_at", now - timedelta(minutes=6)),
            ("issued_at", None),
            ("issued_at", "2026-11-15T10:00:00Z"),
            ("quote_observed_at", now.replace(tzinfo=None)),
            ("sender_signature_verified_at", False),
            ("expires_at", now.replace(tzinfo=None)),
            ("expires_at", now + timedelta(minutes=11)),
        )
        for field, value in invalid:
            with self.subTest(field=field, value=repr(value)):
                original = getattr(self.invoice, field)
                try:
                    setattr(self.invoice, field, value)
                    with self.assertRaises(SettlementRejected):
                        _verify_evidence(self.invoice, self.tx, self.proof)
                finally:
                    setattr(self.invoice, field, original)

    def test_quote_origin_and_sender_signature_identity_are_immutable(self):
        for field, value in (
            ("quote_source", "untrusted-webhook"),
            ("quote_source", None),
            ("sender_challenge_id", "short"),
            ("sender_challenge_id", "bad\nnonce"),
            ("sender_challenge_id", None),
        ):
            with self.subTest(field=field, value=repr(value)):
                original = getattr(self.invoice, field)
                try:
                    setattr(self.invoice, field, value)
                    with self.assertRaises(SettlementRejected):
                        _verify_evidence(self.invoice, self.tx, self.proof)
                finally:
                    setattr(self.invoice, field, original)

    def test_boolean_order_id_cannot_impersonate_first_buyer_order(self):
        original = self.invoice.order_id
        try:
            self.invoice.order_id = 1
            with self.assertRaises(SettlementRejected):
                _verify_evidence(self.invoice, self.tx, {
                    **self.proof, "order_id": True,
                })
        finally:
            self.invoice.order_id = original
