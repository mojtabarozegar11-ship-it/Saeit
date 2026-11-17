"""No-network regression coverage of the XAUUSD review-only owner risk proposal."""
import unittest
from decimal import Decimal as D

from prop_firm.rules import POLICY
from prop_firm.xauusd_owner_risk_review import (
    MAX_OPEN_PERCENT, MAX_SINGLE_PERCENT, PROPOSAL_VERSION,
    review_owner_xauusd_risk,
)


def fixture(**changed):
    args = dict(
        symbol="XAUUSD", account_capital="100",
        equity="100", day_open_equity="100",
        proposed_order_risk_at_stop="1", existing_open_risk_at_stop="0",
        extra_fee_slippage_reserve="0.5", broker_minimum_risk="0.1",
        stop_server_verified=True, broker_snapshot_verified=True,
        broker_lot_verified=True, operative_terms_reconciled=True,
        mode="challenge",
    )
    args.update(changed)
    return review_owner_xauusd_risk(**args)


class OwnerXAUUSDReviewTests(unittest.TestCase):
    def test_01_exact_owner_proposed_caps(self):
        self.assertEqual((MAX_SINGLE_PERCENT, MAX_OPEN_PERCENT), (D("3"), D("8")))

    def test_02_current_policy_still_unchanged(self):
        self.assertEqual((POLICY.order_risk_pct, POLICY.aggregate_risk_pct), (D("0.8"), D("1.6")))
        self.assertFalse(POLICY.real_orders_enabled)

    def test_03_first_order_with_headroom_is_reviewable(self):
        r = fixture()
        self.assertTrue(r.math_and_evidence_ready)
        self.assertEqual(r.projected_equity_at_stop_usd, D("98.5"))
        self.assertFalse(r.real_execution_authorized)
        self.assertFalse(r.challenge_order_submitted)
        self.assertFalse(r.payment_or_funding_authorized)

    def test_04_proposal_thresholds_dollars(self):
        r = fixture()
        self.assertEqual((r.proposed_single_ceiling_usd, r.proposed_open_ceiling_usd), (D("3"), D("8")))
        self.assertEqual((r.daily_equity_floor_usd, r.total_equity_floor_usd), (D("96"), D("92")))

    def test_05_version_is_review_only(self):
        self.assertEqual(fixture().version, PROPOSAL_VERSION)
        self.assertTrue(PROPOSAL_VERSION.startswith("OWNER-XAUUSD-RISK-REVIEW"))

    def test_06_three_percent_order_with_small_buffer_can_fit(self):
        self.assertTrue(fixture(proposed_order_risk_at_stop="3", extra_fee_slippage_reserve=".5").math_and_evidence_ready)

    def test_07_exact_daily_stop_floor_is_a_breach(self):
        r = fixture(proposed_order_risk_at_stop="3", extra_fee_slippage_reserve="1")
        self.assertIn("projected_stop_breaches_daily_floor", r.reasons)

    def test_08_risk_above_three_percent_is_rejected(self):
        r = fixture(proposed_order_risk_at_stop="3.01")
        self.assertIn("proposed_single_cap_exceeded", r.reasons)

    def test_09_aggregate_above_eight_percent_is_rejected(self):
        r = fixture(equity="150", day_open_equity="140", proposed_order_risk_at_stop="3",
                    existing_open_risk_at_stop="5.01", extra_fee_slippage_reserve=".1")
        self.assertIn("proposed_aggregate_cap_exceeded", r.reasons)

    def test_10_eight_percent_is_only_a_ceiling_not_daily_allowance(self):
        r = fixture(proposed_order_risk_at_stop="3", existing_open_risk_at_stop="5",
                    extra_fee_slippage_reserve=".1")
        self.assertIn("projected_stop_breaches_daily_floor", r.reasons)

    def test_11_eight_percent_can_be_mathematically_reviewed_with_gain_headroom(self):
        r = fixture(equity="150", day_open_equity="140", proposed_order_risk_at_stop="3",
                    existing_open_risk_at_stop="5", extra_fee_slippage_reserve=".1")
        self.assertTrue(r.math_and_evidence_ready)
        self.assertFalse(r.real_execution_authorized)

    def test_12_no_slippage_reserve_is_blocked(self):
        self.assertIn("positive_slippage_reserve_required",
                      fixture(extra_fee_slippage_reserve="0").reasons)

    def test_13_negative_slippage_is_invalid(self):
        with self.assertRaises(ValueError):
            fixture(extra_fee_slippage_reserve="-0.01")

    def test_14_negative_existing_risk_is_invalid(self):
        with self.assertRaises(ValueError):
            fixture(existing_open_risk_at_stop="-0.01")

    def test_15_negative_order_risk_is_invalid(self):
        with self.assertRaises(ValueError):
            fixture(proposed_order_risk_at_stop="-1")

    def test_16_zero_order_is_blocked(self):
        self.assertIn("proposed_single_cap_exceeded",
                      fixture(proposed_order_risk_at_stop="0").reasons)

    def test_17_wrong_symbol_rejected(self):
        self.assertIn("xauusd_only", fixture(symbol="XAGUSD").reasons)

    def test_18_symbol_case_is_not_auto_normalized(self):
        self.assertIn("xauusd_only", fixture(symbol="xauusd").reasons)

    def test_19_non_string_symbol_is_invalid(self):
        with self.assertRaises(ValueError):
            fixture(symbol=1234)

    def test_20_unknown_tier_rejected(self):
        self.assertIn("unsupported_account_tier", fixture(account_capital="150").reasons)

    def test_21_float_amount_rejected(self):
        with self.assertRaises(ValueError):
            fixture(proposed_order_risk_at_stop=1.5)

    def test_22_bool_amount_rejected(self):
        with self.assertRaises(ValueError):
            fixture(account_capital=True)

    def test_23_nan_rejected(self):
        with self.assertRaises(ValueError):
            fixture(equity="NaN")

    def test_24_infinity_rejected(self):
        with self.assertRaises(ValueError):
            fixture(equity="Infinity")

    def test_25_daily_floor_already_breached(self):
        self.assertIn("already_breached_daily_floor", fixture(equity="96").reasons)

    def test_26_total_floor_already_breached(self):
        self.assertIn("already_breached_total_floor",
                      fixture(equity="92", day_open_equity="90").reasons)

    def test_27_remaining_daily_headroom_restricts_second_trade(self):
        r = fixture(equity="97", proposed_order_risk_at_stop="1")
        self.assertIn("projected_stop_breaches_daily_floor", r.reasons)

    def test_28_broker_min_lot_risk_must_fit(self):
        self.assertIn("broker_min_lot_risk_exceeds_order",
                      fixture(broker_minimum_risk="1.01").reasons)

    def test_29_stop_must_be_from_trusted_source(self):
        self.assertIn("trusted_stop_missing", fixture(stop_server_verified=False).reasons)

    def test_30_snapshot_must_be_authoritative(self):
        self.assertIn("authoritative_broker_snapshot_missing",
                      fixture(broker_snapshot_verified=False).reasons)

    def test_31_broker_lot_must_be_verified(self):
        self.assertIn("broker_lot_not_verified", fixture(broker_lot_verified=False).reasons)

    def test_32_terms_reconciliation_not_assumed(self):
        self.assertIn("signed_terms_policy_conflict_unresolved",
                      fixture(operative_terms_reconciled=False).reasons)

    def test_33_boolean_like_truthiness_does_not_pass(self):
        self.assertIn("signed_terms_policy_conflict_unresolved",
                      fixture(operative_terms_reconciled=1).reasons)

    def test_34_real_mode_still_denied(self):
        r = fixture(mode="real")
        self.assertFalse(r.math_and_evidence_ready)
        self.assertIn("real_execution_not_enabled_by_review", r.reasons)
        self.assertFalse(r.real_execution_authorized)

    def test_35_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            fixture(mode="paper")

    def test_36_higher_supported_tier_scales_correctly(self):
        r = fixture(account_capital="200", equity="200", day_open_equity="200",
                    proposed_order_risk_at_stop="6", extra_fee_slippage_reserve="1")
        self.assertTrue(r.math_and_evidence_ready)
        self.assertEqual((r.proposed_single_ceiling_usd, r.proposed_open_ceiling_usd), (D("6"), D("16")))

    def test_37_missing_reserve_rejected(self):
        with self.assertRaises(ValueError):
            fixture(extra_fee_slippage_reserve=None)

    def test_38_zero_verified_flags_does_not_enable_order(self):
        r = fixture(stop_server_verified=False, broker_snapshot_verified=False,
                    broker_lot_verified=False, operative_terms_reconciled=False)
        self.assertFalse(r.math_and_evidence_ready)
        self.assertFalse(r.challenge_order_submitted)
        self.assertFalse(r.payment_or_funding_authorized)


if __name__ == "__main__":
    unittest.main()
