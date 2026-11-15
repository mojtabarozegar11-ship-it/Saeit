"""Non-billing catalog value boundaries for the sole educational agent."""
from decimal import Decimal
import unittest

from services.mojtaba_signal_catalog import (
    SignalCatalogError, SignalPlan, get_signal_plan, build_manual_signal_offer,
)

DESC = "Independently sourced educational brief with capital-loss risk and limitations."


class FixedSignalPricePolicyTests(unittest.TestCase):
    def plan(self, price):
        return SignalPlan(
            "education-extra", "Market briefing", "weekly", price, DESC
        )

    def test_existing_commercial_catalog_prices_remain_unchanged(self):
        expected = {"education-weekly": "9.90", "education-monthly": "29.90",
                    "education-quarterly": "79.90"}
        for plan_id, amount in expected.items():
            with self.subTest(plan=plan_id):
                self.assertEqual(
                    build_manual_signal_offer(plan_id)["amount"], amount
                )

    def test_exact_one_cent_and_maximum_price_are_valid(self):
        self.assertEqual(self.plan(Decimal("0.01")).price_usd, Decimal("0.01"))
        self.assertEqual(self.plan(Decimal("10000.00")).price_usd, Decimal("10000.00"))

    def test_missing_or_negative_price_never_builds_an_offer(self):
        for value in (None, False, 1, -1, Decimal("-1"), Decimal("0")):
            with self.subTest(price=value), self.assertRaises(SignalCatalogError):
                self.plan(value)

    def test_subcent_prices_are_rejected_without_rounded_overcharging(self):
        for value in ("0.001", "0.009", "1.001", "9999.999"):
            with self.subTest(price=value), self.assertRaises(SignalCatalogError):
                self.plan(Decimal(value))

    def test_extreme_or_nonfinite_decimal_never_raises_uncaught_error(self):
        for value in ("1E+999999", "1E-999999", "NaN", "Infinity", "-Infinity"):
            with self.subTest(price=value), self.assertRaises(SignalCatalogError):
                self.plan(Decimal(value))

    def test_excessive_quote_price_fails_closed(self):
        for value in ("10000.01", "10001.00", "9999999999999.99"):
            with self.subTest(price=value), self.assertRaises(SignalCatalogError):
                self.plan(Decimal(value))

    def test_catalog_lookup_never_mutates_price_for_manual_quote(self):
        before = get_signal_plan("education-monthly").price_usd
        result = build_manual_signal_offer("education-monthly")
        self.assertFalse(result["payment_enabled"])
        self.assertEqual(get_signal_plan("education-monthly").price_usd, before)
