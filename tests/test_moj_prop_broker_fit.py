"""Minimum broker order risk feasibility — no accounts, orders or network activity."""
import unittest
from decimal import Decimal

from prop_firm.broker_fit import BrokerFitError, check_minimum_broker_order


class MojPropBrokerFitTests(unittest.TestCase):
    def run_fit(self, **overrides):
        values = {
            "tier_index": 0, "broker_min_quantity": "1",
            "broker_quantity_step": "1", "stop_loss_usd_per_unit": "0.25",
            "round_trip_fees_usd": "0.05", "margin_usd_per_unit": "5",
            "available_margin_usd": "100", "currently_open_risk_usd": "0",
            "quote_verified": True, "stop_verified": True,
            "specification_verified": True,
        }
        values.update(overrides)
        return check_minimum_broker_order(**values)

    def test_one_unit_minimum_under_80_cent_risk_is_allowed(self):
        x = self.run_fit()
        self.assertTrue(x.feasible)
        self.assertEqual(x.order_risk_budget_usd, Decimal("0.8"))
        self.assertEqual(x.minimum_trade_loss_usd, Decimal("0.30"))

    def test_minimum_one_micro_lot_exceeds_broker_risk(self):
        x = self.run_fit(broker_min_quantity=1000, broker_quantity_step=1000)
        self.assertFalse(x.feasible)
        self.assertIn("minimum_order_exceeds_single_trade_risk", x.reasons)

    def test_fees_must_be_included_in_loss(self):
        x = self.run_fit(stop_loss_usd_per_unit=".7", round_trip_fees_usd=".2")
        self.assertFalse(x.feasible)
        self.assertEqual(x.minimum_trade_loss_usd, Decimal(".9"))

    def test_aggregate_open_risk_can_block_small_order(self):
        x = self.run_fit(currently_open_risk_usd="1.5")
        self.assertFalse(x.feasible)
        self.assertIn("minimum_order_exceeds_aggregate_risk", x.reasons)

    def test_insufficient_margin_rejects_order(self):
        x = self.run_fit(available_margin_usd="4")
        self.assertFalse(x.feasible)
        self.assertIn("margin_unavailable_for_broker_minimum", x.reasons)

    def test_min_quantity_rounded_up_to_step(self):
        x = self.run_fit(broker_min_quantity="1.1", broker_quantity_step=".5")
        self.assertEqual(x.broker_min_quantity, Decimal("1.5"))
        self.assertEqual(x.minimum_trade_loss_usd, Decimal(".425"))

    def test_missing_verified_quote_rejects(self):
        x = self.run_fit(quote_verified=False)
        self.assertFalse(x.feasible)
        self.assertIn("fresh_verified_broker_spec_quote_stop_required", x.reasons)

    def test_missing_verified_stop_rejects(self):
        self.assertFalse(self.run_fit(stop_verified=False).feasible)

    def test_missing_broker_specification_rejects(self):
        self.assertFalse(self.run_fit(specification_verified=False).feasible)

    def test_truthy_non_boolean_does_not_bypass_verification(self):
        self.assertFalse(self.run_fit(quote_verified=1).feasible)

    def test_higher_capital_increases_loss_budget_not_minimum_lot(self):
        x = self.run_fit(tier_index=10, broker_min_quantity=1000,
                         broker_quantity_step=1000, available_margin_usd=10000)
        self.assertTrue(x.feasible)
        self.assertEqual(x.capital_usd, 50000)
        self.assertEqual(x.order_risk_budget_usd, 400)

    def test_unknown_tier_rejected(self):
        for tier in (-1, 14, True, "0"):
            with self.subTest(tier=tier), self.assertRaises(BrokerFitError):
                self.run_fit(tier_index=tier)

    def test_negative_margin_and_fees_rejected(self):
        with self.assertRaises(BrokerFitError):
            self.run_fit(available_margin_usd=-1)
        with self.assertRaises(BrokerFitError):
            self.run_fit(round_trip_fees_usd=-1)

    def test_float_and_nan_rejected(self):
        for value in ("NaN", .1, "Infinity"):
            with self.subTest(value=value), self.assertRaises(BrokerFitError):
                self.run_fit(broker_min_quantity=value)

    def test_zero_step_and_stop_rejected(self):
        with self.assertRaises(BrokerFitError):
            self.run_fit(broker_quantity_step=0)
        with self.assertRaises(BrokerFitError):
            self.run_fit(stop_loss_usd_per_unit=0)

    def test_no_real_orders_are_placed(self):
        x = self.run_fit()
        self.assertTrue(x.feasible)
        self.assertFalse(hasattr(x, "send_order"))
