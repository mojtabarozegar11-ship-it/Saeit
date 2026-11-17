"""No-order LiteFinance XAUUSD 0.01 lot / $0.80 cap mathematical acceptance tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from scripts.mojprop_litefinance_gold_risk_envelope_d import (
    BrokerRiskUnproven, GoldLotRiskSnapshot
)

NOW = datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc)
SHA = "d62e7a2d9d83926cd3def26f2a619483a1caed7a"


class TestGoldRiskScreen(unittest.TestCase):
    def setUp(self):
        self.quote = GoldLotRiskSnapshot(
            symbol="XAUUSD", quote_currency="USD", account_currency="USD",
            broker_account_type="ECN", quote_timestamp_utc=NOW.isoformat(),
            source_commit=SHA, account_capital_usd="100",
            account_available_margin_usd="80",
            minimum_volume_lots="0.01", lot_step_lots="0.01",
            contract_oz_per_lot="100",
            broker_min_stop_distance_usd_per_oz="0.38",
            quoted_spread_usd_per_oz="0.22",
            anticipated_slippage_usd_per_oz="0.10",
            roundtrip_commission_usd="0.05",
            extra_fee_reserve_usd="0.02",
            margin_for_minimum_lot_usd="25",
            authoritative_account_snapshot=True,
            broker_min_lot_for_account_verified=True,
        )

    def calc(self, snapshot=None, expected=SHA, now=NOW, cap="0.80"):
        return (self.quote if snapshot is None else snapshot).assess(
            expected_source_commit=expected, now=now, max_trade_risk_usd=cap)

    def blocked(self, **kwargs):
        with self.assertRaises(BrokerRiskUnproven):
            self.calc(replace(self.quote, **kwargs))

    def test_math_feasible_but_no_real_trade(self):
        result = self.calc()
        self.assertEqual(result["minimum_exposure_ounces"], "1.00")
        self.assertEqual(result["minimum_risk_at_stop_usd"], "0.7700")
        self.assertTrue(result["minimum_lot_math_possible"])
        for field in ("broker_quote_authenticated_by_this_process", "legal_prop_authorization_verified",
                      "signed_broker_prop_agreement_verified", "independent_capital_and_buffer_verified",
                      "actual_funded_account_ready", "order_execution_authorized",
                      "deployment_authorized", "payment_authorized"):
            self.assertFalse(result[field])

    def test_exact_point_eight_math_only(self):
        self.assertTrue(self.calc(replace(self.quote, broker_min_stop_distance_usd_per_oz="0.41"))["minimum_lot_math_possible"])

    def test_one_cent_over_risk_cap(self):
        self.blocked(broker_min_stop_distance_usd_per_oz="0.42")

    def test_wide_classic_spread_disallows_same_stop(self):
        self.blocked(broker_account_type="CLASSIC", quoted_spread_usd_per_oz="0.42")

    def test_spread_increase_denies(self):
        self.blocked(quoted_spread_usd_per_oz="0.30")

    def test_slippage_increase_denies(self):
        self.blocked(anticipated_slippage_usd_per_oz="0.20")

    def test_roundtrip_commission_increase_denies(self):
        self.blocked(roundtrip_commission_usd="0.10")

    def test_fee_reserve_increase_denies(self):
        self.blocked(extra_fee_reserve_usd="0.10")

    def test_minimum_margin_exceeds_free_margin(self):
        self.blocked(margin_for_minimum_lot_usd="81")

    def test_free_margin_missing(self):
        self.blocked(account_available_margin_usd=None)

    def test_zero_margin_cost_is_unverified(self):
        self.blocked(margin_for_minimum_lot_usd="0")

    def test_zero_capital_denies(self):
        self.blocked(account_capital_usd="0")

    def test_real_account_capital_wrong(self):
        self.blocked(account_capital_usd="200")

    def test_zero_volume_denies(self):
        self.blocked(minimum_volume_lots="0")

    def test_volume_one_tenth_denies_baseline_mismatch(self):
        self.blocked(minimum_volume_lots="0.1")

    def test_minimum_step_wrong(self):
        self.blocked(lot_step_lots="0.001")

    def test_step_larger_than_lot(self):
        self.blocked(lot_step_lots="0.1")

    def test_lot_size_wrong(self):
        self.blocked(contract_oz_per_lot="10")

    def test_symbol_wrong(self):
        self.blocked(symbol="XAUEUR")

    def test_quote_currency_wrong(self):
        self.blocked(quote_currency="EUR")

    def test_account_currency_conversion_unverified(self):
        self.blocked(account_currency="EUR")

    def test_account_type_wrong(self):
        self.blocked(broker_account_type="CENT")

    def test_unsigned_snapshot_denies(self):
        self.blocked(authoritative_account_snapshot=False)

    def test_minimum_lot_not_account_verified(self):
        self.blocked(broker_min_lot_for_account_verified=False)

    def test_boolean_snapshot_denies(self):
        self.blocked(authoritative_account_snapshot="true")

    def test_quote_missing_datetime(self):
        self.blocked(quote_timestamp_utc="")

    def test_quote_timezone_naive(self):
        self.blocked(quote_timestamp_utc="2026-11-17T02:00:00")

    def test_quote_expired(self):
        self.blocked(quote_timestamp_utc=(NOW-timedelta(minutes=6)).isoformat())

    def test_quote_future_denies(self):
        self.blocked(quote_timestamp_utc=(NOW+timedelta(seconds=1)).isoformat())

    def test_quote_timezone_offset_equivalent_works(self):
        q=replace(self.quote,quote_timestamp_utc=NOW.astimezone(timezone(timedelta(hours=3))).isoformat())
        self.assertTrue(self.calc(q)["minimum_lot_math_possible"])

    def test_trusted_time_naive(self):
        with self.assertRaises(BrokerRiskUnproven):
            self.calc(now=datetime(2026,11,17,2,0))

    def test_source_commit_wrong(self):
        self.blocked(source_commit="f"*40)

    def test_expected_commit_wrong(self):
        with self.assertRaises(BrokerRiskUnproven):
            self.calc(expected="f"*40)

    def test_expected_commit_not_sha(self):
        with self.assertRaises(BrokerRiskUnproven):
            self.calc(expected="main")

    def test_spread_float_rejected(self):
        self.blocked(quoted_spread_usd_per_oz=0.22)

    def test_slippage_boolean_rejected(self):
        self.blocked(anticipated_slippage_usd_per_oz=True)

    def test_negative_commission_rejected(self):
        self.blocked(roundtrip_commission_usd="-0.01")

    def test_nan_stop_rejected(self):
        self.blocked(broker_min_stop_distance_usd_per_oz="NaN")

    def test_infinite_spread_rejected(self):
        self.blocked(quoted_spread_usd_per_oz="Infinity")

    def test_cap_above_point_eight_denied(self):
        with self.assertRaises(BrokerRiskUnproven):
            self.calc(cap="0.81")

    def test_smaller_risk_cap_blocks_tighter_budget(self):
        with self.assertRaises(BrokerRiskUnproven):
            self.calc(cap="0.70")

    def test_cap_boolean_denied(self):
        with self.assertRaises(BrokerRiskUnproven):
            self.calc(cap=True)

    def test_zero_total_risk_denied(self):
        self.blocked(broker_min_stop_distance_usd_per_oz="0",quoted_spread_usd_per_oz="0",
                     anticipated_slippage_usd_per_oz="0",roundtrip_commission_usd="0",
                     extra_fee_reserve_usd="0")


if __name__ == "__main__":
    unittest.main()
