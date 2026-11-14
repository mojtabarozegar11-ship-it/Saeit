"""Deterministic, non-financial forward-research model regression suite."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone

from core.mojtrade_forward_metrics import (
    ForwardEvidenceError, MAX_HISTORY, assess_reviewed_history,
)


NOW = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)
START = datetime(2026, 11, 13, 11, 0, tzinfo=timezone.utc)


def snapshot(at=START, btc_close=100, eth_close=200, stance="watch_buy",
             sha_number=1, reviewer_delay_min=7, include_price=True):
    generated = at + timedelta(minutes=5)
    reviewed_at = at + timedelta(minutes=reviewer_delay_min)
    observations = []
    for symbol, close, position, provider in (
        ("BTC/USD", btc_close, stance, "bitstamp-public-ohlc"),
        ("ETH/USD", eth_close, "neutral", "kraken-spot-public-ohlc"),
    ):
        row = {
            "symbol": symbol, "stance": position, "data_source": provider,
            "observed_at": at.isoformat(),
            "signal_id": symbol.replace("/", "-") + "-" + str(sha_number),
            "method": "sma20-sma50-momentum10-v1-closed-1h",
        }
        if include_price:
            row["reference_close_usd"] = close
        observations.append(row)
    return {
        "reviewed_at": reviewed_at.isoformat(),
        "review": {
            "schema": "mojtaba.bot.ai.private-market-research-review.v1",
            "canonical_agent": "economic-master-agent",
            "source_sha256": f"{sha_number:064x}",
            "source_bytes": 700,
            "observations": observations,
            "observation_generated_at": generated.isoformat(),
            "observation_expires_at": (generated + timedelta(minutes=90)).isoformat(),
            "measurement": {"verified_observation_count": 2},
            "controls": {
                "research_only": True, "execution": "disabled", "orders": 0,
                "publication_enabled": False, "delivery_enabled": False,
                "financial_actions_enabled": False,
            },
        },
    }


class ForwardMetricsTests(unittest.TestCase):
    def test_empty_history_cannot_claim_performance_or_revenue(self):
        report = assess_reviewed_history([], NOW)
        self.assertEqual(report["eligible_hypothetical_one_hour_pairs"], 0)
        self.assertIsNone(report["modeled_win_rate_pct"])
        self.assertIsNone(report["verified_trade_pnl"])
        self.assertIsNone(report["collected_revenue"])
        self.assertFalse(report["independently_attested_market_data"])
        self.assertEqual(report["orders"], 0)

    def test_next_closed_hour_has_directional_return_after_declared_costs(self):
        first = snapshot()
        later = snapshot(START + timedelta(hours=1), btc_close=104, stance="neutral",
                         sha_number=2)
        report = assess_reviewed_history([later, first], NOW)
        self.assertEqual(report["eligible_hypothetical_one_hour_pairs"], 1)
        self.assertEqual(report["model"]["round_trip_cost_pct"], "0.3")
        sample = report["recent_reference_samples"][0]
        self.assertEqual(sample["gross_reference_return_pct"], "4.0000")
        self.assertEqual(sample["modeled_net_return_pct"], "3.7000")
        self.assertTrue(sample["modeled_positive_after_cost"])
        self.assertIsNone(report["modeled_win_rate_pct"])

    def test_sell_direction_and_loss_are_modeled_without_an_order(self):
        first = snapshot(stance="watch_sell")
        second = snapshot(START + timedelta(hours=1), btc_close=104,
                          stance="neutral", sha_number=2)
        report = assess_reviewed_history([first, second], NOW)
        sample = report["recent_reference_samples"][0]
        self.assertEqual(sample["gross_reference_return_pct"], "-4.0000")
        self.assertEqual(sample["modeled_net_return_pct"], "-4.3000")
        self.assertFalse(sample["modeled_positive_after_cost"])
        self.assertEqual(report["orders"], 0)

    def test_neutral_stance_does_not_create_backfilled_trade(self):
        one = snapshot(stance="neutral")
        two = snapshot(START + timedelta(hours=1), btc_close=120, stance="neutral",
                       sha_number=2)
        self.assertEqual(assess_reviewed_history([one, two], NOW)[
            "eligible_hypothetical_one_hour_pairs"], 0)

    def test_no_future_close_no_model_return(self):
        self.assertEqual(assess_reviewed_history([snapshot()], NOW)[
            "eligible_hypothetical_one_hour_pairs"], 0)
        later = snapshot(START + timedelta(hours=2), btc_close=103,
                         stance="neutral", sha_number=2)
        self.assertEqual(assess_reviewed_history([snapshot(), later], NOW)[
            "eligible_hypothetical_one_hour_pairs"], 0)

    def test_late_first_review_cannot_hindsight_trade(self):
        one = snapshot(reviewer_delay_min=61)
        two = snapshot(START + timedelta(hours=1), btc_close=104,
                       stance="neutral", sha_number=2, reviewer_delay_min=7)
        self.assertEqual(assess_reviewed_history([one, two], NOW)[
            "eligible_hypothetical_one_hour_pairs"], 0)

    def test_source_hash_replay_never_counts_extra_pairs(self):
        one = snapshot()
        two = snapshot(START + timedelta(hours=1), btc_close=104,
                       stance="neutral", sha_number=2)
        repeated = copy.deepcopy(one)
        report = assess_reviewed_history([one, repeated, two], NOW)
        self.assertEqual(report["repeated_source_snapshots_ignored"], 1)
        self.assertEqual(report["eligible_hypothetical_one_hour_pairs"], 1)

    def test_same_candle_later_review_cannot_cherry_pick_price(self):
        first = snapshot()
        late = snapshot(btc_close=999, sha_number=3, reviewer_delay_min=8)
        two = snapshot(START + timedelta(hours=1), btc_close=104,
                       stance="neutral", sha_number=2)
        report = assess_reviewed_history([late, two, first], NOW)
        self.assertEqual(report["recent_reference_samples"][0]["modeled_net_return_pct"],
                         "3.7000")

    def test_legacy_without_close_never_invents_history(self):
        old = snapshot(include_price=False)
        new = snapshot(START + timedelta(hours=1), btc_close=104,
                       stance="neutral", sha_number=2)
        report = assess_reviewed_history([old, new], NOW)
        self.assertEqual(report["legacy_snapshots_without_usd_close"], 1)
        self.assertEqual(report["eligible_hypothetical_one_hour_pairs"], 0)

    def test_reject_forged_prices_and_fake_market_quote(self):
        for bad in (-1, 0, True, "100", float("nan"), float("inf"), 1e20):
            item = snapshot()
            item["review"]["observations"][0]["reference_close_usd"] = bad
            with self.subTest(bad=str(bad)), self.assertRaisesRegex(
                ForwardEvidenceError, "MODEL_USD_CLOSE_INVALID"
            ):
                assess_reviewed_history([item], NOW)
        item = snapshot()
        item["review"]["observations"][0]["data_source"] = "binance-public-klines"
        with self.assertRaisesRegex(ForwardEvidenceError, "MODEL_USD_PROVIDER_INVALID"):
            assess_reviewed_history([item], NOW)

    def test_json_roundtrip_production_values_pass_strict_boundary(self):
        first = json.loads(json.dumps(snapshot()))
        second = json.loads(json.dumps(snapshot(
            START + timedelta(hours=1), btc_close=104,
            stance="neutral", sha_number=2,
        )))
        outcome = assess_reviewed_history([first, second], NOW)
        self.assertEqual(outcome["eligible_hypothetical_one_hour_pairs"], 1)
        self.assertEqual(outcome["recent_reference_samples"][0][
            "modeled_net_return_pct"], "3.7000")

    def test_numeric_zero_is_not_equivalent_to_false(self):
        item = json.loads(json.dumps(snapshot()))
        item["review"]["controls"]["orders"] = False
        with self.assertRaisesRegex(
            ForwardEvidenceError, "MODEL_EXECUTION_BOUNDARY_INVALID"
        ):
            assess_reviewed_history([item], NOW)

    def test_reject_wrong_agent_or_financial_execution_flags(self):
        for field, value in (
            ("canonical_agent", "new-trading-bot"),
            ("controls.orders", 1),
            ("controls.publication_enabled", True),
            ("controls.financial_actions_enabled", True),
        ):
            item = snapshot()
            if "." in field:
                _, sub = field.split(".", 1)
                item["review"]["controls"][sub] = value
            else:
                item["review"][field] = value
            with self.subTest(field=field), self.assertRaises(ForwardEvidenceError):
                assess_reviewed_history([item], NOW)

    def test_reject_unsealed_or_future_review_and_source_overlong(self):
        for key in ("future", "expiry", "naive", "unsealed"):
            item = snapshot()
            if key == "future":
                item["reviewed_at"] = (NOW + timedelta(minutes=1)).isoformat()
            elif key == "expiry":
                item["review"]["observation_expires_at"] = (START + timedelta(days=1)).isoformat()
            elif key == "naive":
                item["reviewed_at"] = "2026-11-13T11:07:00"
            else:
                item["review"]["source_sha256"] = "not_sha256"
            with self.subTest(key=key), self.assertRaises(ForwardEvidenceError):
                assess_reviewed_history([item], NOW)

    def test_reject_oversized_input_or_missing_fields(self):
        with self.assertRaisesRegex(ForwardEvidenceError, "HISTORY_LIMIT"):
            assess_reviewed_history([snapshot()] * (MAX_HISTORY + 1), NOW)
        invalid = snapshot()
        invalid["review"]["observations"][0]["symbol"] = "BTC/USDT"
        with self.assertRaisesRegex(ForwardEvidenceError, "MODEL_SYMBOL_ORDER"):
            assess_reviewed_history([invalid], NOW)

    def test_model_win_rate_only_after_minimum_30_observed_pairs(self):
        t0 = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
        history = [
            snapshot(t0 + timedelta(hours=i), btc_close=100 + i, eth_close=200,
                     stance="watch_buy", sha_number=i + 100)
            for i in range(31)
        ]
        report = assess_reviewed_history(history, NOW)
        self.assertEqual(report["eligible_hypothetical_one_hour_pairs"], 30)
        self.assertEqual(report["modeled_win_rate_pct"], "100.00")
        self.assertIsNotNone(report["modeled_mean_net_return_pct"])
        self.assertIsNone(report["verified_win_rate"])
        self.assertIsNone(report["verified_trade_pnl"])
        self.assertFalse(report["independently_attested_market_data"])


class CanonicalHandoffReportTests(unittest.TestCase):
    def test_new_canonical_reviews_can_pair_without_claiming_live_pnl(self):
        first = snapshot()
        first["review"]["canonical_agent"] = "mojtaba-bot-ai"
        next_hour = snapshot(START + timedelta(hours=1), btc_close=104,
                             stance="neutral", sha_number=2)
        next_hour["review"]["canonical_agent"] = "mojtaba-bot-ai"
        result = assess_reviewed_history([first, next_hour], NOW)
        self.assertEqual(result["eligible_hypothetical_one_hour_pairs"], 1)
        self.assertIsNone(result["verified_trade_pnl"])
        self.assertIsNone(result["collected_revenue"])
        self.assertEqual(result["orders"], 0)

    def test_mixed_legacy_and_canonical_reviews_do_not_reset_history(self):
        legacy = snapshot()
        canonical = snapshot(START + timedelta(hours=1), btc_close=104,
                             stance="neutral", sha_number=2)
        canonical["review"]["canonical_agent"] = "mojtaba-bot-ai"
        result = assess_reviewed_history([canonical, legacy], NOW)
        self.assertEqual(result["eligible_hypothetical_one_hour_pairs"], 1)
        self.assertEqual(result["recent_reference_samples"][0]["modeled_net_return_pct"],
                         "3.7000")

if __name__ == "__main__":
    unittest.main()
