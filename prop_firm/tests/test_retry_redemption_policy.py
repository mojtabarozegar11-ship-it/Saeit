"""Pure retry entitlement regression checks; no DB, RPC, or payment."""
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from prop_firm.retry_redemption_policy import (
    ChallengeOutcome, RetryEvidence, RetryNotEligible, require_failed_retry,
)


class RetryRedemptionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.valid = RetryEvidence(
            challenge_id="challenge-1", identity_id="buyer-1",
            outcome=ChallengeOutcome.FAILED,
            final_at=datetime(2026, 11, 22, tzinfo=timezone.utc),
            redemption_used=False, dispute_open=False,
            original_payment_final=True,
        )

    def test_final_paid_failure_can_be_considered_for_atomic_claim(self):
        self.assertEqual(require_failed_retry(self.valid, buyer_identity_id="buyer-1"),
                         "challenge-1")

    def test_other_buyer_cannot_redeem(self):
        with self.assertRaises(RetryNotEligible):
            require_failed_retry(self.valid, buyer_identity_id="buyer-2")

    def test_only_failed_outcome_qualifies(self):
        for outcome in (ChallengeOutcome.PASSED, ChallengeOutcome.ACTIVE,
                        ChallengeOutcome.VOID, "failed"):
            with self.subTest(outcome=outcome), self.assertRaises(RetryNotEligible):
                require_failed_retry(replace(self.valid, outcome=outcome),
                                     buyer_identity_id="buyer-1")

    def test_used_disputed_or_unpaid_rejected(self):
        for change in ({"redemption_used": True}, {"dispute_open": True},
                       {"original_payment_final": False}):
            with self.subTest(change=change), self.assertRaises(RetryNotEligible):
                require_failed_retry(replace(self.valid, **change),
                                     buyer_identity_id="buyer-1")

    def test_future_dated_final_failure_is_not_redeemable(self):
        future = replace(self.valid, final_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
        with self.assertRaises(RetryNotEligible):
            require_failed_retry(future, buyer_identity_id="buyer-1")

    def test_invalid_evidence_fails_closed(self):
        for change in ({"final_at": None}, {"final_at": datetime(2026, 11, 22)},
                       {"redemption_used": 1}, {"dispute_open": 0},
                       {"original_payment_final": 1}, {"challenge_id": ""}):
            with self.subTest(change=change), self.assertRaises(RetryNotEligible):
                require_failed_retry(replace(self.valid, **change),
                                     buyer_identity_id="buyer-1")


if __name__ == "__main__":
    unittest.main()
