import unittest
from decimal import Decimal

try:
    from moj_prop_contract import (
        ChallengeDecision,
        ChallengeSnapshot,
        ChallengeState,
        PropContractError,
        PropEnrollment,
        PropRules,
        activate_enrollment,
        advance_state,
        evaluate_challenge,
        next_funded_tier,
        validate_enrollment,
        validate_rules,
    )
except ModuleNotFoundError:
    from core.moj_prop_contract import (
        ChallengeDecision,
        ChallengeSnapshot,
        ChallengeState,
        PropContractError,
        PropEnrollment,
        PropRules,
        activate_enrollment,
        advance_state,
        evaluate_challenge,
        next_funded_tier,
        validate_enrollment,
        validate_rules,
    )


class MojPropContractTests(unittest.TestCase):
    def rules(self, **changes):
        values = {"profit_target_pct": Decimal("10")}
        values.update(changes)
        return PropRules(**values)

    def enrollment(self, **changes):
        values = {
            "challenge_id": "challenge-52",
            "customer_id": "customer-52",
            "rules": self.rules(),
        }
        values.update(changes)
        return PropEnrollment(**values)

    def snapshot(self, **changes):
        values = {
            "initial_equity_usd": Decimal("100"),
            "start_of_day_equity_usd": Decimal("110"),
            "current_equity_usd": Decimal("108"),
            "peak_equity_usd": Decimal("110"),
            "trading_days": 5,
        }
        values.update(changes)
        return ChallengeSnapshot(**values)

    def test_known_base_rules_are_valid(self):
        validate_rules(self.rules())

    def test_fee_must_be_thirty_trx(self):
        with self.assertRaisesRegex(PropContractError, "challenge_fee_must_be_30_trx"):
            validate_rules(self.rules(challenge_fee_trx=Decimal("29")))

    def test_funded_account_must_be_in_ladder(self):
        with self.assertRaisesRegex(PropContractError, "funded_account_not_in_tier_ladder"):
            validate_rules(self.rules(funded_account_usd=Decimal("150")))

    def test_daily_loss_must_be_below_drawdown(self):
        with self.assertRaisesRegex(PropContractError, "daily_loss_must_be_below_max_drawdown"):
            validate_rules(self.rules(daily_loss_limit_pct=Decimal("10"), max_drawdown_pct=Decimal("10")))

    def test_float_is_rejected(self):
        with self.assertRaisesRegex(PropContractError, "challenge_fee_trx_must_be_decimal_like"):
            validate_rules(self.rules(challenge_fee_trx=30.0))

    def test_risk_per_trade_cannot_exceed_daily_loss(self):
        with self.assertRaisesRegex(PropContractError, "risk_per_trade_exceeds_daily_loss"):
            validate_rules(self.rules(max_risk_per_trade_pct=Decimal("6")))

    def test_next_tier_from_base(self):
        self.assertEqual(next_funded_tier(Decimal("100")), Decimal("200"))

    def test_next_tier_is_monotonic(self):
        self.assertEqual(next_funded_tier(Decimal("800")), Decimal("1500"))

    def test_last_tier_has_no_next_tier(self):
        self.assertIsNone(next_funded_tier(Decimal("20000")))

    def test_unknown_tier_is_rejected(self):
        with self.assertRaisesRegex(PropContractError, "current_account_not_in_tier_ladder"):
            next_funded_tier(Decimal("999"))

    def test_enrollment_is_valid_before_release(self):
        validate_enrollment(self.enrollment())

    def test_invalid_identity_is_rejected(self):
        with self.assertRaisesRegex(PropContractError, "challenge_id_invalid"):
            validate_enrollment(self.enrollment(challenge_id="bad id"))

    def test_public_wallet_is_rejected(self):
        with self.assertRaisesRegex(PropContractError, "public_wallet_prohibited"):
            validate_enrollment(self.enrollment(public_wallet_published=True))

    def test_automatic_payment_is_rejected(self):
        with self.assertRaisesRegex(PropContractError, "automatic_payment_disabled"):
            validate_enrollment(self.enrollment(automatic_payment_enabled=True))

    def test_verified_fee_requires_transaction_id(self):
        with self.assertRaisesRegex(PropContractError, "verified_fee_requires_transaction_id"):
            validate_enrollment(self.enrollment(fee_payment_verified=True))

    def test_fee_transaction_id_is_validated(self):
        validate_enrollment(self.enrollment(fee_payment_verified=True, transaction_id="trx-52-proof"))

    def test_active_release_requires_all_gates(self):
        with self.assertRaisesRegex(PropContractError, "release_gates_incomplete"):
            validate_enrollment(self.enrollment(state=ChallengeState.ACTIVE))

    def test_eligible_can_activate_with_all_gates(self):
        enrolled = self.enrollment(
            state=ChallengeState.ELIGIBLE,
            fee_payment_verified=True,
            kyc_approved=True,
            legal_reviewed=True,
            owner_approved=True,
            rights_cleared=True,
            transaction_id="trx-52-proof",
        )
        activated = activate_enrollment(enrolled)
        self.assertEqual(activated.state, ChallengeState.ACTIVE)

    def test_activation_requires_eligible_state(self):
        with self.assertRaisesRegex(PropContractError, "enrollment_not_eligible"):
            activate_enrollment(self.enrollment())

    def test_challenge_stays_active_below_target(self):
        result = evaluate_challenge(self.rules(), self.snapshot(current_equity_usd=Decimal("108")))
        self.assertEqual(result.decision, ChallengeDecision.ACTIVE)
        self.assertEqual(result.reason, "challenge_in_progress")

    def test_target_requires_minimum_days(self):
        result = evaluate_challenge(self.rules(), self.snapshot(current_equity_usd=Decimal("110"), trading_days=4))
        self.assertEqual(result.decision, ChallengeDecision.ACTIVE)

    def test_target_and_minimum_days_pass(self):
        result = evaluate_challenge(self.rules(), self.snapshot(current_equity_usd=Decimal("110")))
        self.assertEqual(result.decision, ChallengeDecision.PASSED)
        self.assertEqual(result.reason, "profit_target_reached")

    def test_daily_loss_limit_fails_at_boundary(self):
        result = evaluate_challenge(self.rules(), self.snapshot(start_of_day_equity_usd=Decimal("100"), current_equity_usd=Decimal("95"), peak_equity_usd=Decimal("110")))
        self.assertEqual(result.decision, ChallengeDecision.FAILED)
        self.assertEqual(result.reason, "daily_loss_limit_breached")

    def test_max_drawdown_fails_at_boundary(self):
        result = evaluate_challenge(self.rules(), self.snapshot(start_of_day_equity_usd=Decimal("100"), current_equity_usd=Decimal("99"), peak_equity_usd=Decimal("110")))
        self.assertEqual(result.decision, ChallengeDecision.FAILED)
        self.assertEqual(result.reason, "max_drawdown_breached")

    def test_zero_equity_fails(self):
        result = evaluate_challenge(self.rules(), self.snapshot(current_equity_usd=Decimal("0")))
        self.assertEqual(result.reason, "equity_zero")

    def test_maximum_days_fails(self):
        result = evaluate_challenge(self.rules(), self.snapshot(trading_days=31))
        self.assertEqual(result.reason, "maximum_trading_days_exceeded")

    def test_peak_cannot_be_below_current_equity(self):
        with self.assertRaisesRegex(PropContractError, "peak_equity_inconsistent"):
            evaluate_challenge(self.rules(), self.snapshot(current_equity_usd=Decimal("111"), peak_equity_usd=Decimal("110")))

    def test_state_cannot_skip_to_funded(self):
        with self.assertRaisesRegex(PropContractError, "invalid_challenge_transition"):
            advance_state(ChallengeState.CREATED, ChallengeState.FUNDED)

    def test_state_progression_is_explicit(self):
        self.assertEqual(advance_state(ChallengeState.CREATED, ChallengeState.PAYMENT_PENDING), ChallengeState.PAYMENT_PENDING)
        self.assertEqual(advance_state(ChallengeState.ACTIVE, ChallengeState.PASSED), ChallengeState.PASSED)

    def test_failed_state_is_terminal(self):
        with self.assertRaisesRegex(PropContractError, "invalid_challenge_transition"):
            advance_state(ChallengeState.FAILED, ChallengeState.ACTIVE)


if __name__ == "__main__":
    unittest.main()
