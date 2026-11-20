import unittest
from decimal import Decimal as D

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


if __name__ == "__main__":
    unittest.main()
