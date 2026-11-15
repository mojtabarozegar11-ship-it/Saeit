"""Contract tests for a fixed educational signal catalog."""
from decimal import Decimal
import unittest

from services.mojtaba_signal_catalog import (
    PLANS, SignalCatalogError, SignalPlan, build_manual_signal_offer, get_signal_plan,
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

    def test_future_plans_cannot_hide_market_risk_or_promise_profit(self):
        for description in (
            "Twelve individually reviewed briefs with provenance and limitations.",
            "Guaranteed market returns with no risk under any economic scenario.",
            "a" * 801,
            "",
        ):
            with self.subTest(description=description), self.assertRaises(SignalCatalogError):
                SignalPlan(
                    "education-extended", "Extended market research",
                    "monthly", Decimal("19.90"), description,
                )

    def test_new_plan_requires_known_cadence_and_canonical_identifier(self):
        description = "Twelve reviewed educational reports, with market-risk disclosure and independent source records."
        for plan_id, cadence in (
            ("INVALID PLAN", "monthly"), ("education-extended", "continuous"),
            (None, "weekly"), ("education-extended", 7),
        ):
            with self.subTest(plan_id=plan_id, cadence=cadence), self.assertRaises(SignalCatalogError):
                SignalPlan(plan_id, "Research plan", cadence, Decimal("19.90"), description)


    def test_catalog_rejects_malformed_unicode_before_publication(self):
        description = "Reviewed educational market report with explicit capital risk and sources."
        for field in ("title", "description"):
            for surrogate in (chr(0xD800), chr(0xDFFF)):
                with self.subTest(field=field, surrogate=hex(ord(surrogate))):
                    values = {
                        "plan_id": "education-extended",
                        "title": "Research plan",
                        "cadence": "monthly",
                        "price_usd": Decimal("19.90"),
                        "description": description,
                    }
                    values[field] += surrogate
                    with self.assertRaises(SignalCatalogError):
                        SignalPlan(**values)

    def test_single_bot_identity_requires_a_literal_string(self):
        class Impersonator:
            def __eq__(self, value):
                return value == "mojtaba.bot.ai"
        with self.assertRaises(SignalCatalogError):
            build_manual_signal_offer("education-weekly", agent=Impersonator())

if __name__ == "__main__":
    unittest.main()
