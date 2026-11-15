"""AGR-01 deterministic client-data economics, not estimated actual market data."""
from dataclasses import replace
from decimal import Decimal
from django.test import SimpleTestCase

from core.agriculture_service_economics import (
    FarmEnterpriseInputs, FarmEconomicsInputError, assess_farm_enterprise,
)


class AgricultureEnterpriseProductTests(SimpleTestCase):
    def scenario(self, **changes):
        values = {
            "area_hectares": "2",
            "production_tonnes_per_hectare": "5",
            "farmgate_price_per_tonne": "100",
            "variable_cost_per_hectare": "200",
            "fixed_cost_total": "100",
            "irrigation_m3_per_hectare": "2000",
            "currency_code": "USD",
        }
        values.update(changes)
        return FarmEnterpriseInputs(**values)

    def test_customer_enterprise_reconciles_price_cost_and_operating_surplus(self):
        r = assess_farm_enterprise(self.scenario())
        self.assertEqual(r.currency_code, "USD")
        self.assertEqual(r.gross_revenue, "1000.00")
        self.assertEqual(r.variable_cost_total, "400.00")
        self.assertEqual(r.total_cost, "500.00")
        self.assertEqual(r.operating_surplus, "500.00")
        self.assertEqual(r.contribution_per_tonne, "60.00")

    def test_break_even_yield_and_water_productivity_have_correct_units(self):
        r = assess_farm_enterprise(self.scenario())
        self.assertEqual(r.break_even_yield_tonnes_per_hectare, "2.500")
        self.assertEqual(r.water_productivity_kg_per_m3, "2.500")

    def test_price_and_yield_shocks_are_explicit_10pct_scenarios(self):
        r = assess_farm_enterprise(self.scenario())
        self.assertEqual(r.price_down_10pct_surplus, "400.00")
        self.assertEqual(r.yield_down_10pct_surplus, "400.00")
        self.assertEqual(r.combined_price_and_yield_down_10pct_surplus, "310.00")
        self.assertEqual(r.operating_margin_pct, "50.00")

    def test_loss_making_farm_reports_negative_not_guaranteed_profit(self):
        r = assess_farm_enterprise(self.scenario(fixed_cost_total="2000"))
        self.assertEqual(r.operating_surplus, "-1400.00")
        self.assertFalse(r.forecast_or_profit_guaranteed)
        self.assertFalse(r.buyer_payment_collected)

    def test_zero_output_is_not_a_fake_contribution(self):
        r = assess_farm_enterprise(self.scenario(production_tonnes_per_hectare="0"))
        self.assertEqual(r.gross_revenue, "0.00")
        self.assertEqual(r.contribution_per_tonne, "undefined_no_production")
        self.assertIsNone(r.operating_margin_pct)

    def test_zero_farmgate_price_has_no_break_even_yield(self):
        r = assess_farm_enterprise(self.scenario(farmgate_price_per_tonne="0"))
        self.assertIsNone(r.break_even_yield_tonnes_per_hectare)
        self.assertEqual(r.operating_surplus, "-500.00")

    def test_zero_irrigation_input_refused_in_per_water_unit_analysis(self):
        with self.assertRaises(FarmEconomicsInputError):
            assess_farm_enterprise(self.scenario(irrigation_m3_per_hectare="0"))

    def test_negative_area_yield_price_costs_refused(self):
        for field in ("area_hectares", "production_tonnes_per_hectare",
                      "farmgate_price_per_tonne", "variable_cost_per_hectare",
                      "fixed_cost_total", "irrigation_m3_per_hectare"):
            with self.subTest(field=field), self.assertRaises(FarmEconomicsInputError):
                assess_farm_enterprise(self.scenario(**{field: "-1"}))

    def test_floats_bool_and_nonfinite_inputs_refused(self):
        for value in (1.2, True, "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(FarmEconomicsInputError):
                assess_farm_enterprise(self.scenario(farmgate_price_per_tonne=value))

    def test_unbounded_input_sizes_refused(self):
        for key, value in (
            ("area_hectares", "100000001"),
            ("production_tonnes_per_hectare", "10000001"),
            ("farmgate_price_per_tonne", "1000000000001"),
            ("fixed_cost_total", "1000000000001"),
        ):
            with self.subTest(key=key), self.assertRaises(FarmEconomicsInputError):
                assess_farm_enterprise(self.scenario(**{key: value}))

    def test_currency_unit_is_preserved_not_silently_converted(self):
        t = assess_farm_enterprise(self.scenario(currency_code="TOMAN"))
        self.assertEqual(t.currency_code, "TOMAN")
        with self.assertRaises(FarmEconomicsInputError):
            assess_farm_enterprise(self.scenario(currency_code="BTC"))

    def test_input_source_is_unverified_not_realized_revenue(self):
        r = assess_farm_enterprise(self.scenario())
        self.assertEqual(r.inputs_provenance, "customer_supplied_not_independently_verified")
        self.assertFalse(r.buyer_payment_collected)
        self.assertFalse(r.forecast_or_profit_guaranteed)
