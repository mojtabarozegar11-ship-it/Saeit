"""No-order regression checks for the additive v1.3 XAUUSD risk review."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from prop_firm.xauusd_v13_preflight import (
    DRAFT_CONTRACT_VERSION, GoldOrderSnapshot, review_gold_order,
)

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def candidate(**overrides):
    data = dict(
        product="MOJ-PROP-01", contract_version=DRAFT_CONTRACT_VERSION,
        symbol="XAUUSD", account_currency="USD", initial_capital="100",
        equity="100", day_open_equity="100", existing_open_remaining_stop_risk="0",
        side="buy", mid_price_per_oz="4000", stop_price_per_oz="3998.10",
        lot_quantity="0.01", minimum_lot="0.01", lot_step="0.01",
        ounces_per_lot="100", min_stop_distance_per_oz="0.2",
        full_spread_per_oz="0.3", slippage_reserve_per_oz="0.2",
        roundtrip_fees_usd="0.1", margin_required_usd="25", free_margin_usd="75",
        quote_at=NOW, assessed_at=NOW, broker_snapshot_claimed=True,
        complete_open_positions_claimed=True, symbol_spec_claimed=True,
        stop_claimed=True,
    )
    data.update(overrides)
    return GoldOrderSnapshot(**data)


class DraftRiskTests(unittest.TestCase):
    def test_single_risk_3_dollars(self):
        d = review_gold_order(candidate())
        self.assertTrue(d.mathematically_admissible)
        self.assertEqual((d.order_risk_usd, d.max_single_usd, d.max_open_usd),
                         (D("2.5"), D("3"), D("8")))
        self.assertFalse(d.real_orders_enabled)
        self.assertFalse(d.checkout_enabled)
        self.assertFalse(d.funding_enabled)
        self.assertFalse(d.contract_binding_enabled)
        self.assertFalse(d.independent_broker_verified)

    def test_exact_3_percent_with_4_percent_daily_room(self):
        d = review_gold_order(candidate(stop_price_per_oz="3997.60"))
        self.assertEqual(d.order_risk_usd, D("3.00"))
        self.assertTrue(d.mathematically_admissible)

    def test_one_cent_above_3_percent(self):
        d = review_gold_order(candidate(stop_price_per_oz="3997.59"))
        self.assertIn("trade_exceeds_3pct", d.reasons)

    def test_two_open_3_dollar_risks_rejected_by_daily_limit(self):
        d = review_gold_order(candidate(stop_price_per_oz="3997.60",
                    existing_open_remaining_stop_risk="3"))
        self.assertIn("projected_stops_breach_drawdown_limit", d.reasons)

    def test_open_risk_over_eight_percent(self):
        d = review_gold_order(candidate(existing_open_remaining_stop_risk="6"))
        self.assertIn("open_positions_exceed_8pct", d.reasons)

    def test_eight_percent_aggregate_possible_only_with_equity_cushion(self):
        d = review_gold_order(candidate(existing_open_remaining_stop_risk="5.5",
                                         equity="109", day_open_equity="100"))
        self.assertTrue(d.mathematically_admissible)
        self.assertEqual(d.open_risk_usd, D("8.0"))

    def test_eight_percent_aggregate_rejected_without_intraday_cushion(self):
        d = review_gold_order(candidate(existing_open_remaining_stop_risk="5.5",
                                         equity="109", day_open_equity="109"))
        self.assertIn("projected_stops_breach_drawdown_limit", d.reasons)

    def test_zero_drawdown_headroom_rejected(self):
        d = review_gold_order(candidate(equity="96"))
        self.assertIn("account_already_at_drawdown_limit", d.reasons)

    def test_old_contract_not_accepted(self):
        with self.assertRaises(ValueError):
            review_gold_order(candidate(contract_version="2026-11-15/v1.2"))

    def test_educational_sku_not_accepted(self):
        with self.assertRaises(ValueError):
            review_gold_order(candidate(product="MOJPROP-STARTER30"))

    def test_not_xauusd(self):
        self.assertIn("xauusd_usd_only",review_gold_order(candidate(symbol="EURUSD")).reasons)

    def test_currency_conversion_not_assumed(self):
        self.assertIn("xauusd_usd_only",review_gold_order(candidate(account_currency="EUR")).reasons)

    def test_invalid_sell_stop(self):
        self.assertIn("stop_on_wrong_side",review_gold_order(candidate(side="sell")).reasons)

    def test_verified_stop_distance(self):
        self.assertIn("broker_min_stop_distance_rejected",review_gold_order(candidate(min_stop_distance_per_oz="3")).reasons)

    def test_margin_shortfall(self):
        self.assertIn("insufficient_verified_free_margin",review_gold_order(candidate(free_margin_usd="20")).reasons)

    def test_lot_step(self):
        self.assertIn("broker_lot_step_rejected",review_gold_order(candidate(lot_quantity="0.015")).reasons)

    def test_missing_broker_snapshot(self):
        self.assertIn("unreconciled_snapshot_claims",review_gold_order(candidate(broker_snapshot_claimed=False)).reasons)

    def test_truthy_fake_verification_rejected(self):
        self.assertIn("unreconciled_snapshot_claims",review_gold_order(candidate(broker_snapshot_claimed=1)).reasons)

    def test_quote_stale(self):
        self.assertIn("stale_or_future_quote",review_gold_order(candidate(quote_at=NOW-timedelta(minutes=6))).reasons)

    def test_quote_future(self):
        self.assertIn("stale_or_future_quote",review_gold_order(candidate(quote_at=NOW+timedelta(seconds=1))).reasons)

    def test_naive_quote(self):
        self.assertIn("timezone_aware_quote_required",review_gold_order(candidate(quote_at=NOW.replace(tzinfo=None))).reasons)

    def test_negative_fee(self):
        with self.assertRaises(ValueError):
            review_gold_order(candidate(roundtrip_fees_usd="-0.1"))

    def test_float_evidence(self):
        with self.assertRaises(ValueError):
            review_gold_order(candidate(lot_quantity=0.01))

    def test_nan(self):
        with self.assertRaises(ValueError):
            review_gold_order(candidate(free_margin_usd="NaN"))

    def test_no_capital_promise_from_math(self):
        d=review_gold_order(candidate())
        self.assertFalse(d.funding_enabled)

    def test_wrong_starting_tier(self):
        self.assertIn("plan1_initial_capital_only",review_gold_order(candidate(initial_capital="200")).reasons)

if __name__ == "__main__":
    unittest.main()
