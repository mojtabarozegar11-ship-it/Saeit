"""A153: worst-case stop-out must never exhaust v1.2 drawdown floors.

All values are isolated arithmetic test fixtures (NOT LiteFinance quotes,
live positions, connected accounts, or independently verified broker data).
No transport, trading, payment, or migration operations are performed.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from prop_firm.rules import POLICY, authorize_order


class OrderDrawdownHeadroomTests(SimpleTestCase):
    def review(self, **overrides):
        values = {
            "account_capital": "100",
            "equity": "100",
            "day_open_equity": "100",
            "risk_at_stop": "0.4",
            "open_risk_before": "0.2",
            "broker_minimum_risk": "0.1",
            "verified_stop": True,
            "authoritative_snapshot": True,
            "mode": "challenge",
        }
        values.update(overrides)
        return authorize_order(**values)

    def test_01_safe_simulation_still_allowed_without_any_trade_side_effect(self):
        decision = self.review()
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.daily_equity_floor, Decimal("96"))
        self.assertEqual(decision.total_equity_floor, Decimal("92"))
        self.assertFalse(hasattr(decision, "execute"))

    def test_02_daily_stop_out_exactly_on_four_percent_floor_is_rejected(self):
        decision = self.review(equity="96.60")
        self.assertFalse(decision.allowed)
        self.assertIn("stop_risk_exceeds_drawdown_headroom", decision.reasons)
        self.assertNotIn("daily_loss_floor_reached", decision.reasons)

    def test_03_daily_stop_out_one_cent_above_floor_is_allowed(self):
        self.assertTrue(self.review(equity="96.61").allowed)

    def test_04_total_stop_out_exactly_on_eight_percent_floor_is_rejected(self):
        decision = self.review(equity="92.60", day_open_equity="95")
        self.assertFalse(decision.allowed)
        self.assertIn("stop_risk_exceeds_drawdown_headroom", decision.reasons)
        self.assertNotIn("total_loss_floor_reached", decision.reasons)

    def test_05_total_stop_out_one_cent_above_floor_is_allowed(self):
        self.assertTrue(self.review(equity="92.61", day_open_equity="95").allowed)

    def test_06_existing_open_position_risk_is_counted_with_new_order(self):
        decision = self.review(equity="96.40", open_risk_before="0.2",
                               risk_at_stop="0.2")
        self.assertFalse(decision.allowed)
        self.assertIn("stop_risk_exceeds_drawdown_headroom", decision.reasons)

    def test_07_open_risk_cannot_be_discarded_to_allow_same_order(self):
        safe = self.review(equity="96.50", open_risk_before="0",
                           risk_at_stop="0.2")
        unsafe = self.review(equity="96.50", open_risk_before="0.4",
                             risk_at_stop="0.2")
        self.assertTrue(safe.allowed)
        self.assertFalse(unsafe.allowed)

    def test_08_higher_daily_open_mark_drives_dynamic_daily_floor(self):
        decision = self.review(equity="106.60", day_open_equity="110")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.daily_equity_floor, Decimal("106"))

    def test_09_large_level_preserves_absolute_four_percent_headroom(self):
        denied = self.review(account_capital="100000", equity="96050",
                             day_open_equity="100000", risk_at_stop="50",
                             open_risk_before="0")
        approved = self.review(account_capital="100000", equity="96050.01",
                               day_open_equity="100000", risk_at_stop="50",
                               open_risk_before="0")
        self.assertFalse(denied.allowed)
        self.assertTrue(approved.allowed)

    def test_10_max_per_trade_risk_remains_independent_08_percent_cap(self):
        decision = self.review(equity="100", risk_at_stop="0.81")
        self.assertFalse(decision.allowed)
        self.assertIn("per_order_risk_limit", decision.reasons)

    def test_11_aggregate_risk_remains_independent_16_percent_cap(self):
        decision = self.review(equity="100", risk_at_stop="0.7",
                               open_risk_before="1")
        self.assertFalse(decision.allowed)
        self.assertIn("aggregate_risk_limit", decision.reasons)

    def test_12_missing_authoritative_broker_snapshot_blocks_even_safe_headroom(self):
        decision = self.review(authoritative_snapshot=False)
        self.assertFalse(decision.allowed)
        self.assertIn("authoritative_broker_snapshot_required", decision.reasons)

    def test_13_missing_verified_stop_blocks_even_safe_headroom(self):
        decision = self.review(verified_stop=False)
        self.assertFalse(decision.allowed)
        self.assertIn("stop_loss_required", decision.reasons)

    def test_14_real_execution_hard_off_even_when_all_math_gates_pass(self):
        decision = self.review(mode="real", execution_authorized=True)
        self.assertFalse(decision.allowed)
        self.assertIn("real_execution_disabled", decision.reasons)
        self.assertFalse(POLICY.real_orders_enabled)
        self.assertFalse(POLICY.trx_checkout_enabled)

    def test_15_real_mode_cannot_override_headroom_failure(self):
        decision = self.review(equity="96.60", mode="real",
                               execution_authorized=True)
        self.assertFalse(decision.allowed)
        self.assertIn("real_execution_disabled", decision.reasons)
        self.assertIn("stop_risk_exceeds_drawdown_headroom", decision.reasons)

    def test_16_imprecise_float_equity_is_rejected_not_silently_rounded(self):
        with self.assertRaises(ValueError):
            self.review(equity=96.61)

    def test_17_negative_or_float_open_risk_is_rejected(self):
        for value in ("-0.1", 0.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.review(open_risk_before=value)

    def test_18_invalid_nonfinite_stop_is_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.review(risk_at_stop=value)

    def test_19_breached_equity_cannot_get_back_to_allowed_through_small_stop(self):
        decision = self.review(equity="96.0", risk_at_stop="0.01",
                               open_risk_before="0")
        self.assertFalse(decision.allowed)
        self.assertIn("daily_loss_floor_reached", decision.reasons)

    def test_20_total_floor_dominates_when_daily_floor_is_lower(self):
        decision = self.review(equity="92.4", day_open_equity="94",
                               open_risk_before="0.1", risk_at_stop="0.3")
        self.assertFalse(decision.allowed)
        self.assertIn("stop_risk_exceeds_drawdown_headroom", decision.reasons)
        self.assertEqual(decision.total_equity_floor, Decimal("92"))
        self.assertEqual(decision.daily_equity_floor, Decimal("90"))

    def test_21_broker_minimum_lot_risk_still_blocks_math_safe_order(self):
        decision = self.review(broker_minimum_risk="0.5",
                               risk_at_stop="0.4")
        self.assertFalse(decision.allowed)
        self.assertIn("broker_minimum_lot_not_feasible", decision.reasons)
