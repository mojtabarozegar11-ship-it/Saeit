"""Illustrative, unmeasured farm-enterprise arithmetic and safety checks."""
from dataclasses import replace
from decimal import Decimal
import unittest

from .farm_enterprise_budget import (
    FarmBudgetError, FarmScenario, budget, compare_scenarios,
)

# Invented exercise values, NOT observed agriculture, actual TRX, or a forecast.
def sample(scenario_id="baseline"):
    return FarmScenario(
        scenario_id=scenario_id, crop_id="example_crop", season_id="season_2026",
        currency="USD", provenance="planning_assumption",
        area_ha="2", yield_kg_per_ha="4000", farmgate_price_per_kg="0.50",
        irrigation_m3_per_ha="3000", water_cost_per_m3="0.10",
        energy_kwh_per_ha="400", energy_cost_per_kwh="0.20",
        other_variable_cost_per_ha="1000", allocated_fixed_cost_per_ha="400",
    )


class EnterpriseBudgetRegressions(unittest.TestCase):
    def test_gross_return_is_yield_times_price(self):
        r = budget(sample())["per_ha_and_total"]
        self.assertEqual(r["gross_return_per_ha"], "2000.000000")
        self.assertEqual(r["gross_return_total"], "4000.000000")

    def test_water_and_energy_costs_are_separate_operating_inputs(self):
        r = budget(sample())["per_ha_and_total"]
        self.assertEqual(r["irrigation_cost_per_ha"], "300.000000")
        self.assertEqual(r["energy_cost_per_ha"], "80.000000")

    def test_gross_margin_excludes_allocated_fixed_costs(self):
        r = budget(sample())["per_ha_and_total"]
        self.assertEqual(r["variable_cost_per_ha"], "1380.000000")
        self.assertEqual(r["gross_margin_per_ha"], "620.000000")

    def test_net_return_subtracts_explicit_allocated_fixed_costs(self):
        r = budget(sample())["per_ha_and_total"]
        self.assertEqual(r["total_cost_per_ha"], "1780.000000")
        self.assertEqual(r["net_return_after_allocated_costs_per_ha"], "220.000000")
        self.assertEqual(r["net_return_after_allocated_costs_total"], "440.000000")

    def test_crop_water_productivity_keeps_physical_units(self):
        r = budget(sample())["per_ha_and_total"]
        self.assertEqual(r["water_productivity_kg_per_m3"], "1.333333")
        self.assertEqual(r["water_volume_total_m3"], "6000.000000")
        self.assertEqual(r["production_total_kg"], "8000.000000")

    def test_break_even_price_and_yield_are_algebraically_consistent(self):
        r = budget(sample())["per_ha_and_total"]
        self.assertEqual(r["break_even_price_per_kg"], "0.445000")
        self.assertEqual(r["break_even_yield_kg_per_ha"], "3560.000000")

    def test_zero_yield_has_no_finite_break_even_price(self):
        s = replace(sample(), yield_kg_per_ha=Decimal("0"))
        self.assertIsNone(budget(s)["per_ha_and_total"]["break_even_price_per_kg"])

    def test_zero_price_has_no_finite_break_even_yield(self):
        s = replace(sample(), farmgate_price_per_kg=Decimal("0"))
        self.assertIsNone(budget(s)["per_ha_and_total"]["break_even_yield_kg_per_ha"])

    def test_zero_water_has_undefined_water_productivity_not_infinity(self):
        s = replace(sample(), irrigation_m3_per_ha=Decimal("0"))
        self.assertIsNone(budget(s)["per_ha_and_total"]["water_productivity_kg_per_m3"])

    def test_negative_net_return_is_preserved_not_clamped(self):
        s = replace(sample(), yield_kg_per_ha=Decimal("1"))
        self.assertLess(Decimal(budget(s)["per_ha_and_total"]["net_return_after_allocated_costs_per_ha"]), 0)

    def test_comparison_tracks_alternative_less_water_not_automatic_savings(self):
        alternative = replace(
            sample("alternative"), irrigation_m3_per_ha=Decimal("2500"),
            yield_kg_per_ha=Decimal("4200"), energy_kwh_per_ha=Decimal("350"),
        )
        r = compare_scenarios(sample(), alternative)
        self.assertEqual(r["differences_alternative_minus_baseline"]["delta_water_m3_per_ha"], "-500.000000")
        self.assertEqual(r["differences_alternative_minus_baseline"]["delta_net_return_per_ha"], "160.000000")
        self.assertFalse(r["field_water_savings_verified"])
        self.assertFalse(r["causal_effect_claimed"])

    def test_input_digest_is_deterministic(self):
        self.assertEqual(budget(sample())["input_digest_sha256"],
                         budget(sample())["input_digest_sha256"])
        self.assertEqual(len(budget(sample())["input_digest_sha256"]), 64)

    def test_changed_cost_changes_source_digest(self):
        changed = replace(sample(), energy_cost_per_kwh=Decimal("0.25"))
        self.assertNotEqual(budget(sample())["input_digest_sha256"],
                            budget(changed)["input_digest_sha256"])

    def test_floats_bool_dict_and_none_are_rejected_in_cost_inputs(self):
        for bad in (1.5, True, False, None, {}, []):
            with self.subTest(v=repr(bad)), self.assertRaises(FarmBudgetError):
                replace(sample(), water_cost_per_m3=bad)

    def test_nonfinite_negative_and_overprecision_inputs_rejected(self):
        for bad in ("NaN", "Infinity", "1e5", "-1", "0.0000001", "01", " 1 "):
            with self.subTest(v=bad), self.assertRaises(FarmBudgetError):
                replace(sample(), water_cost_per_m3=bad)

    def test_decimal_nonfinite_direct_values_fail_closed(self):
        for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with self.subTest(v=repr(bad)), self.assertRaises(FarmBudgetError):
                replace(sample(), water_cost_per_m3=bad)

    def test_area_must_be_strictly_positive(self):
        for bad in ("0", "-1", "0.0000001", True, None):
            with self.subTest(area=repr(bad)), self.assertRaises(FarmBudgetError):
                replace(sample(), area_ha=bad)

    def test_input_e12_ceiling_does_not_crash_decimal_accounting(self):
        s = replace(sample(), water_cost_per_m3="1000000000000")
        self.assertIn("per_ha_and_total", budget(s))
        with self.assertRaises(FarmBudgetError):
            replace(sample(), water_cost_per_m3="1000000000001")

    def test_scenario_identity_injection_and_unicode_surrogates_rejected(self):
        for bad in ("bad id", "bad\nname", "x", "BAD", "x" * 70, "a" + chr(0xD800)):
            with self.subTest(id=repr(bad)), self.assertRaises(FarmBudgetError):
                replace(sample(), scenario_id=bad)

    def test_currency_is_explicit_and_never_auto_converted(self):
        s = replace(sample(), currency="TOMAN")
        self.assertEqual(budget(s)["currency"], "TOMAN")
        with self.assertRaises(FarmBudgetError):
            replace(sample(), currency="TRX")

    def test_provenance_is_explicit_and_never_trusted_as_field_validation(self):
        for provenance in ("synthetic", "planning_assumption", "unverified_user_record"):
            r = budget(replace(sample(), provenance=provenance))
            self.assertFalse(r["input_values_verified"])
            self.assertFalse(r["field_efficacy_verified"])
            self.assertFalse(r["realized_income_verified"])
        with self.assertRaises(FarmBudgetError):
            replace(sample(), provenance="peer_reviewed_field_proof")

    def test_comparison_rejects_mixed_currencies(self):
        with self.assertRaises(FarmBudgetError):
            compare_scenarios(sample(), replace(sample("alternative"), currency="IRR"))

    def test_comparison_rejects_different_crop(self):
        with self.assertRaises(FarmBudgetError):
            compare_scenarios(sample(), replace(sample("alternative"), crop_id="different_crop"))

    def test_comparison_rejects_different_season(self):
        with self.assertRaises(FarmBudgetError):
            compare_scenarios(sample(), replace(sample("alternative"), season_id="season_2027"))

    def test_comparison_rejects_different_area(self):
        with self.assertRaises(FarmBudgetError):
            compare_scenarios(sample(), replace(sample("alternative"), area_ha=Decimal("3")))

    def test_comparison_rejects_reused_scenario_identifier(self):
        with self.assertRaises(FarmBudgetError):
            compare_scenarios(sample(), sample())

    def test_comparison_requires_two_authorized_scenario_types(self):
        for other in (None, {}, "alternative", True):
            with self.subTest(other=repr(other)), self.assertRaises(FarmBudgetError):
                compare_scenarios(sample(), other)

    def test_zero_cost_budget_has_zero_break_even_and_no_forced_profit(self):
        s = replace(sample(), water_cost_per_m3=Decimal("0"),
                    energy_cost_per_kwh=Decimal("0"),
                    other_variable_cost_per_ha=Decimal("0"),
                    allocated_fixed_cost_per_ha=Decimal("0"))
        r = budget(s)["per_ha_and_total"]
        self.assertEqual(r["break_even_price_per_kg"], "0.000000")
        self.assertEqual(r["break_even_yield_kg_per_ha"], "0.000000")

    def test_core_arithmetic_never_marks_revenue_as_cash_collected(self):
        r = budget(sample())
        self.assertNotIn("payment_received", r)
        self.assertFalse(r["realized_income_verified"])
        self.assertFalse(r["all_fixed_costs_independently_verified"])


if __name__ == "__main__":
    unittest.main()
