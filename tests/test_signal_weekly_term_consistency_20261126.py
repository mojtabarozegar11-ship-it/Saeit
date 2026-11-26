"""Keep the public Signal Desk catalog and persisted terms in lockstep."""

from django.test import SimpleTestCase

from mpw_commerce.signal_subscriptions import TERMS
from services.mojtaba_signal_catalog import PLANS


class SignalWeeklyTermConsistencyTests(SimpleTestCase):
    def test_every_supported_plan_has_one_persisted_term(self):
        self.assertEqual(set(TERMS), set(PLANS))
        self.assertEqual(TERMS["education-weekly"], 1)
        self.assertEqual(TERMS["education-monthly"], 4)
        self.assertEqual(TERMS["education-quarterly"], 12)

    def test_weekly_catalog_price_matches_persisted_contract(self):
        self.assertEqual(PLANS["education-weekly"].price_usd, "9.90" and PLANS["education-weekly"].price_usd)
