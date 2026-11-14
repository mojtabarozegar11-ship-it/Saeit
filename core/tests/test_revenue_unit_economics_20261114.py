"""Zero-I/O regressions for strict, no-fabricated-revenue unit economics."""
from decimal import Decimal
from unittest import TestCase

from core.revenue_unit_economics import compute_quote_scenario


def quote(**changes):
    baseline = {
        "currency": "USD",
        "base_unit_price": "100.00",
        "discount_percent": "10",
        "direct_unit_cost": "30",
        "delivery_unit_cost": "5",
        "payment_unit_fee": "2",
        "refund_unit_reserve": "3",
        "tax_unit_reserve": "5",
        "period_fixed_cost": "180",
        "expected_units": 5,
    }
    baseline.update(changes)
    return baseline


class StrictQuoteScenarioTests(TestCase):
    def test_correct_contribution(self):
        x = compute_quote_scenario(quote())
        self.assertEqual(x["unit_price"], "90.00")
        self.assertEqual(x["variable_unit_cost"], "45.00")
        self.assertEqual(x["unit_contribution"], "45.00")

    def test_break_even_ceiling(self):
        self.assertEqual(compute_quote_scenario(quote())["break_even_units"], 4)

    def test_month_result_after_fixed_cost(self):
        self.assertEqual(compute_quote_scenario(quote())["estimated_operating_result"], "45.00")

    def test_gross_sales_not_cash(self):
        x = compute_quote_scenario(quote())
        self.assertEqual(x["estimated_gross_sales"], "450.00")
        self.assertIsNone(x["external_cash_settlement"])
        self.assertIsNone(x["verified_net_profit"])

    def test_all_cost_fields_are_counted(self):
        x = compute_quote_scenario(quote(payment_unit_fee="12"))
        self.assertEqual(x["variable_unit_cost"], "55.00")
        self.assertEqual(x["unit_contribution"], "35.00")

    def test_zero_discount(self):
        self.assertEqual(compute_quote_scenario(quote(discount_percent=0))["unit_price"], "100.00")

    def test_full_discount_not_viable(self):
        x = compute_quote_scenario(quote(discount_percent=100))
        self.assertFalse(x["unit_economics_viable"])
        self.assertIsNone(x["break_even_units"])

    def test_negative_contribution_not_viable(self):
        x = compute_quote_scenario(quote(direct_unit_cost="101"))
        self.assertLess(Decimal(x["unit_contribution"]), 0)
        self.assertIsNone(x["break_even_units"])

    def test_no_units_does_not_create_sales(self):
        x = compute_quote_scenario(quote(expected_units=0))
        self.assertEqual(x["estimated_gross_sales"], "0.00")
        self.assertEqual(x["estimated_operating_result"], "-180.00")

    def test_zero_fixed_break_even_zero(self):
        self.assertEqual(compute_quote_scenario(quote(period_fixed_cost=0))["break_even_units"], 0)

    def test_half_up_rounding_for_usd(self):
        x = compute_quote_scenario(quote(base_unit_price="1.005", discount_percent="0", direct_unit_cost=0,
              delivery_unit_cost=0, payment_unit_fee=0, refund_unit_reserve=0,
              tax_unit_reserve=0, period_fixed_cost=0))
        self.assertEqual(x["unit_price"], "1.01")

    def test_toman_precision_is_not_rial_conversion(self):
        x = compute_quote_scenario(quote(currency="IRT"))
        self.assertEqual(x["unit_price"], "90")
        self.assertEqual(x["currency"], "IRT")

    def test_rial_currency_is_separate(self):
        self.assertEqual(compute_quote_scenario(quote(currency="IRR"))["currency"], "IRR")

    def test_trx_six_decimal_precision(self):
        x = compute_quote_scenario(quote(currency="TRX", base_unit_price="0.123456",
           discount_percent="0", direct_unit_cost=0, delivery_unit_cost=0,
           payment_unit_fee=0, refund_unit_reserve=0, tax_unit_reserve=0, period_fixed_cost=0))
        self.assertEqual(x["unit_price"], "0.123456")

    def test_reject_unknown_currency(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(currency="EUR"))

    def test_reject_case_shifting_currency(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(currency="usd"))

    def test_reject_floating_money(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(base_unit_price=3.14))

    def test_reject_boolean_money(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(direct_unit_cost=True))

    def test_reject_negative_money(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(direct_unit_cost="-1"))

    def test_reject_percent_above_100(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(discount_percent="100.01"))

    def test_reject_infinite_decimal(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(period_fixed_cost=Decimal("Infinity")))

    def test_reject_missing_fields(self):
        values = quote()
        del values["direct_unit_cost"]
        with self.assertRaises(ValueError):
            compute_quote_scenario(values)

    def test_reject_unknown_fields_including_fake_cash_proof(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(verified_revenue=1000))

    def test_reject_negative_expected_units(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(expected_units=-1))

    def test_reject_float_expected_units(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(expected_units=1.0))

    def test_reject_excessively_large_expected_units(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(expected_units=1000001))

    def test_reject_bool_expected_units(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(expected_units=True))

    def test_reject_exponential_number(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(base_unit_price="1e20"))

    def test_reject_oversized_number(self):
        with self.assertRaises(ValueError):
            compute_quote_scenario(quote(base_unit_price="9"*20))

    def test_positive_contribution_but_below_break_even(self):
        x = compute_quote_scenario(quote(expected_units=1))
        self.assertTrue(x["unit_economics_viable"])
        self.assertFalse(x["scenario_reaches_break_even"])

    def test_positive_contribution_meets_break_even(self):
        self.assertTrue(compute_quote_scenario(quote(expected_units=4))["scenario_reaches_break_even"])

    def test_no_automatic_price_or_spend_authorization(self):
        x = compute_quote_scenario(quote())
        self.assertTrue(x["requires_owner_approval_for_price_and_spend"])
        self.assertEqual(x["financial_claim"], "SCENARIO_ONLY_NOT_RECEIPT")


class ConservativeMoneyCycle02Tests(TestCase):
    """Close underpricing gaps without inventing sold units or cash."""

    def test_five_fractional_costs_round_up_individually(self):
        x = compute_quote_scenario(quote(
            discount_percent=0, direct_unit_cost="0.001",
            delivery_unit_cost="0.001", payment_unit_fee="0.001",
            refund_unit_reserve="0.001", tax_unit_reserve="0.001",
        ))
        self.assertEqual(x["variable_unit_cost"], "0.05")

    def test_fractional_fixed_cost_rounds_up(self):
        x = compute_quote_scenario(quote(period_fixed_cost="0.001"))
        self.assertEqual(x["period_fixed_cost"], "0.01")

    def test_break_even_shortfall_calculated(self):
        x = compute_quote_scenario(quote(expected_units=1))
        self.assertEqual(x["break_even_units_shortfall"], 3)

    def test_reached_break_even_has_zero_shortfall(self):
        x = compute_quote_scenario(quote(expected_units=5))
        self.assertEqual(x["break_even_units_shortfall"], 0)

    def test_never_claim_shortfall_when_not_viable(self):
        x = compute_quote_scenario(quote(direct_unit_cost=150))
        self.assertIsNone(x["break_even_units_shortfall"])

    def test_minimum_price_for_target_volume(self):
        x = compute_quote_scenario(quote(expected_units=5))
        self.assertEqual(x["minimum_unit_sale_price_for_expected_units"], "81.00")

    def test_zero_target_has_no_minimum_price(self):
        x = compute_quote_scenario(quote(expected_units=0))
        self.assertIsNone(x["minimum_unit_sale_price_for_expected_units"])

    def test_contribution_margin_percentage(self):
        x = compute_quote_scenario(quote())
        self.assertEqual(x["contribution_margin_percent"], "50.00")

    def test_zero_price_has_no_margin_percentage(self):
        x = compute_quote_scenario(quote(discount_percent=100))
        self.assertIsNone(x["contribution_margin_percent"])

    def test_trx_cost_never_rounds_down_to_zero(self):
        x = compute_quote_scenario(quote(
            currency="TRX", base_unit_price="1",
            discount_percent=0, direct_unit_cost="0.0000001",
            delivery_unit_cost=0, payment_unit_fee=0,
            refund_unit_reserve=0, tax_unit_reserve=0,
        ))
        self.assertEqual(x["variable_unit_cost"], "0.000001")

    def test_cost_component_breakdown_matches_total(self):
        x = compute_quote_scenario(quote())
        items = x["cost_components_rounded_up"]
        self.assertEqual(sum(map(Decimal, items.values())), Decimal(x["variable_unit_cost"]))
