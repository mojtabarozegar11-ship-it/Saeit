import unittest
from decimal import Decimal as D
from datetime import datetime, timedelta

from prop_firm.simulation_readiness import (
    ReadinessInputs, SyntheticReplayFeed, evaluate_readiness,
)


class ReadinessTests(unittest.TestCase):
    def test_internal_replay_is_allowed_but_not_sale(self):
        result = evaluate_readiness(ReadinessInputs(mode="internal_replay"))
        self.assertTrue(result.internal_replay_allowed)
        self.assertFalse(result.customer_admission_allowed)
        self.assertFalse(result.checkout_enabled)
        self.assertIn("not_authoritative", result.blockers[0])

    def test_external_sale_is_fail_closed(self):
        result = evaluate_readiness(ReadinessInputs())
        self.assertFalse(result.internal_replay_allowed)
        self.assertFalse(result.customer_admission_allowed)
        self.assertFalse(result.checkout_enabled)
        self.assertEqual(len(result.blockers), 5)

    def test_external_sale_requires_all_gates(self):
        result = evaluate_readiness(ReadinessInputs(
            provider_verified=True, license_verified=True,
            reward_reserve_verified=True, legal_review_verified=True,
            anti_tamper_operational=True,
        ))
        self.assertTrue(result.customer_admission_allowed)
        self.assertTrue(result.checkout_enabled)
        self.assertEqual(result.blockers, ())

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_readiness(ReadinessInputs(mode="live"))

    def test_replay_is_deterministic_and_bounded(self):
        feed = SyntheticReplayFeed(count=3, start_price="100",
                                   spread="1", step="0.25")
        quotes = list(feed)
        self.assertEqual(len(quotes), 3)
        self.assertEqual(quotes[0].bid, D("99.5"))
        self.assertEqual(quotes[2].ask, D("101.0"))
        self.assertFalse(feed.production_authoritative)

    def test_replay_rejects_empty_count(self):
        with self.assertRaises(ValueError):
            SyntheticReplayFeed(count=0)

    def test_non_boolean_confirmation_never_enables_sale(self):
        confirmed = dict(provider_verified=True, license_verified=True,
                         reward_reserve_verified=True, legal_review_verified=True,
                         anti_tamper_operational=True)
        for field in confirmed:
            for bad in ("false", "true", 1, [], {}, None):
                with self.subTest(field=field, bad=bad):
                    values = dict(confirmed, **{field: bad})
                    decision = evaluate_readiness(ReadinessInputs(**values))
                    self.assertFalse(decision.customer_admission_allowed)
                    self.assertFalse(decision.checkout_enabled)
                    self.assertEqual(len(decision.blockers), 1)

    def test_replay_clock_rolls_over_minute_hour_and_day(self):
        quotes = list(SyntheticReplayFeed(count=86400, step="0"))
        self.assertEqual(quotes[59].timestamp, "2026-11-19T00:01:00Z")
        self.assertEqual(quotes[3599].timestamp, "2026-11-19T01:00:00Z")
        self.assertEqual(quotes[-1].timestamp, "2026-11-20T00:00:00Z")
        for first, second in zip(quotes, quotes[1:]):
            self.assertEqual(datetime.fromisoformat(second.timestamp) -
                             datetime.fromisoformat(first.timestamp),
                             timedelta(seconds=1))

    def test_replay_rejects_invalid_count_symbol_and_prices(self):
        for params in ({"count": True}, {"count": 1.5}, {"count": 86401},
                       {"symbol": " "}, {"symbol": None},
                       {"spread": "NaN"}, {"step": "Infinity"},
                       {"start_price": "bad"}, {"start_price": "0.5"},
                       {"start_price": "1", "spread": "1", "step": "-0.5",
                        "count": 2}):
            with self.subTest(params=params):
                with self.assertRaises(ValueError):
                    SyntheticReplayFeed(**params)


if __name__ == "__main__":
    unittest.main()
