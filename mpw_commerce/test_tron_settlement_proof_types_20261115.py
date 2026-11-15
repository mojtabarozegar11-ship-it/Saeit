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
            total_usd=Decimal("29.00"), sender_challenge_id="challenge-101",
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
