"""MojPlayWin product contribution, fee and monthly sales calculations."""
from decimal import Decimal
from django.test import SimpleTestCase

from core.commercial_unit_economics import estimate_digital_sale


class CommercialUnitEconomicsTests(SimpleTestCase):
    def calculate(self, **changes):
        kwargs = dict(
            price_usd="7.50", hypothetical_sales=100,
            processor_fee_percent="1", network_fee_usd=".10",
            fulfillment_usd=".10", support_usd=".25",
            refund_reserve_percent="2", acquisition_usd=".50",
            monthly_fixed_cost_usd="20", target_net_usd="3500",
        )
        kwargs.update(changes)
        return estimate_digital_sale(**kwargs)

    def test_margins_subtract_every_explicit_cost(self):
        x = self.calculate()
        self.assertEqual(x.revenue_usd, Decimal("750"))
        self.assertEqual(x.per_sale_cost_usd, Decimal("1.18"))
        self.assertEqual(x.contribution_per_sale_usd, Decimal("6.32"))
        self.assertEqual(x.month_net_estimate_usd, Decimal("612"))
        self.assertTrue(x.assumptions_only)

    def test_stated_goal_requires_ceil_number_of_sales(self):
        x = self.calculate()
        self.assertEqual(x.units_for_target_net, 557)
        self.assertEqual(x.breakeven_units, 4)

    def test_negative_contribution_yields_no_breakeven_promise(self):
        x = self.calculate(network_fee_usd="10")
        self.assertLess(x.contribution_per_sale_usd, 0)
        self.assertIsNone(x.breakeven_units)
        self.assertIsNone(x.units_for_target_net)

    def test_processor_fee_and_refund_reserve_considered(self):
        x = self.calculate(processor_fee_percent="10", refund_reserve_percent="20")
        self.assertEqual(x.per_sale_cost_usd, Decimal("3.20"))

    def test_round_variable_cost_up_not_down(self):
        x = self.calculate(price_usd="4", processor_fee_percent=".01",
                           refund_reserve_percent=0, network_fee_usd=0,
                           fulfillment_usd=0, support_usd=0, acquisition_usd=0)
        self.assertEqual(x.per_sale_cost_usd, Decimal(".01"))

    def test_never_infer_actual_sales(self):
        x = self.calculate(hypothetical_sales=0)
        self.assertEqual(x.revenue_usd, 0)
        self.assertTrue(x.assumptions_only)

    def test_zero_fixed_cost_can_breakeven_before_first_sale(self):
        x = self.calculate(monthly_fixed_cost_usd=0, target_net_usd=0)
        self.assertEqual(x.breakeven_units, 0)

    def test_invalid_sales_counts_rejected(self):
        for invalid in (-1, True, "100", 1.0):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.calculate(hypothetical_sales=invalid)

    def test_float_monetary_values_rejected(self):
        for invalid in (1.5, float("inf"), float("nan")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.calculate(price_usd=invalid)

    def test_nonpositive_price_rejected(self):
        for invalid in ("0", "-4"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.calculate(price_usd=invalid)

    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(network_fee_usd="-1")

    def test_fractional_percent_over_hundred_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(processor_fee_percent=101)

    def test_refund_reserve_over_hundred_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(refund_reserve_percent=101)

    def test_cannot_promise_break_even_when_contribution_exactly_zero(self):
        x = self.calculate(price_usd="4", processor_fee_percent=0,
                           refund_reserve_percent=0, network_fee_usd="4",
                           fulfillment_usd=0, support_usd=0, acquisition_usd=0)
        self.assertEqual(x.contribution_per_sale_usd, 0)
        self.assertIsNone(x.breakeven_units)

    def test_no_mixing_trx_and_usd(self):
        # Caller's currency assumption is USD. TRX quotes need separate evidence.
        x = self.calculate(price_usd="6.80")
        self.assertEqual(x.price_usd, Decimal("6.80"))
        self.assertFalse(hasattr(x, "trx_received"))

    def test_one_sale_is_not_enough_to_recover_fixed_cost(self):
        x = self.calculate(hypothetical_sales=1)
        self.assertLess(x.month_net_estimate_usd, 0)
