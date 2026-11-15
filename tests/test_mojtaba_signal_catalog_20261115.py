"""Contract tests for a fixed educational signal catalog."""
from decimal import Decimal
import unittest

from services.mojtaba_signal_catalog import (
    PLANS, SignalCatalogError, build_manual_signal_offer, get_signal_plan,
)

class SignalCatalogTests(unittest.TestCase):
    def test_catalog_has_three_explicit_plans(self):
        self.assertEqual(set(PLANS), {
            "education-weekly", "education-monthly", "education-quarterly"
        })
        self.assertEqual(get_signal_plan("education-weekly").price_usd, Decimal("9.90"))

    def test_unknown_plan_cannot_be_sold(self):
        with self.assertRaises(SignalCatalogError):
            get_signal_plan("gold-profit-guaranteed")

    def test_offer_uses_single_agent_and_fixed_price(self):
        offer = build_manual_signal_offer("education-monthly")
        self.assertEqual(offer["agent"], "mojtaba.bot.ai")
        self.assertEqual(offer["amount"], "29.90")
        self.assertEqual(offer["commercial_stage"], "manual_offer_only")
        self.assertTrue(offer["contract_required"])

    def test_offer_does_not_enable_payment_or_trading(self):
        offer = build_manual_signal_offer("education-weekly")
        self.assertFalse(offer["payment_enabled"])
        self.assertFalse(offer["publication_allowed"])
        self.assertFalse(offer["trading_enabled"])
        self.assertFalse(offer["delivery_confirmed"])

    def test_another_agent_cannot_publish_the_catalog(self):
        with self.assertRaises(SignalCatalogError):
            build_manual_signal_offer("education-weekly", agent="another.bot")

    def test_plan_prices_are_decimal_minor_units(self):
        for plan in PLANS.values():
            self.assertIs(type(plan.price_usd), Decimal)
            self.assertEqual(plan.price_usd, plan.price_usd.quantize(Decimal("0.01")))

    def test_catalog_text_does_not_claim_guaranteed_returns(self):
        for plan in PLANS.values():
            self.assertNotIn("guaranteed", plan.description.casefold())
            self.assertIn("risk", plan.description.casefold())

if __name__ == "__main__":
    unittest.main()
