"""Pure calculation regressions; synthetic only, no client/customer records."""
import importlib.util
from pathlib import Path
import unittest

_MODULE = Path(__file__).resolve().parents[1] / "scripts" / "farm_profitability_private_service_report_20261108.py"
_SPEC = importlib.util.spec_from_file_location("farm_private_service", _MODULE)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def baseline():
    return {
        "currency": "TOMAN",
        "area_hectares": "2",
        "harvested_kg": "500",
        "sold_kg": "400",
        "price_per_kg": "5",
        "fixed_costs": {"irrigation": "1500"},
        "production_variable_costs": {"seed": "300"},
        "per_sold_kg_costs": {"transport": "0.5"},
        "all_material_costs_documented": False,
    }


class FarmPrivateReportTests(unittest.TestCase):
    def test_decimal_context_is_not_leaked_to_other_calculators(self):
        from decimal import getcontext

        original_precision = getcontext().prec
        try:
            getcontext().prec = 28
            self.assertEqual(mod.calculate(baseline())["operating_contribution"], "0.00")
            self.assertEqual(getcontext().prec, 28)
        finally:
            getcontext().prec = original_precision

    def test_break_even_and_cost_scope(self):
        result = mod.calculate(baseline())
        self.assertEqual(result["operating_contribution"], "0.00")
        self.assertEqual(result["break_even_sold_kg"], "400.00")
        self.assertEqual(result["margin_of_safety_percent"], "0.00")
        self.assertFalse(result["economic_net_profit_computed"])
        self.assertEqual(result["decision_gate"], "COST_DATA_INCOMPLETE_NO_COMMERCIAL_ACCEPTANCE")

    def test_unachievable_break_even_must_be_explicit(self):
        data = baseline()
        data["per_sold_kg_costs"]["transport"] = "5"
        result = mod.calculate(data)
        self.assertIsNone(result["break_even_sold_kg"])
        self.assertFalse(result["break_even_possible_at_supplied_price"])

    def test_sold_quantity_cannot_exceed_harvest(self):
        data = baseline()
        data["sold_kg"] = "501"
        with self.assertRaises(mod.InputError):
            mod.calculate(data)

    def test_nan_infinity_and_oversized_exponent_are_rejected(self):
        for value in ("NaN", "Infinity", "1e100", "-1", "1e9999999999"):
            with self.subTest(value=value):
                data = baseline()
                data["price_per_kg"] = value
                with self.assertRaises(mod.InputError):
                    mod.calculate(data)

    def test_empty_costs_do_not_produce_fake_margin(self):
        data = baseline()
        for field in ("fixed_costs", "production_variable_costs", "per_sold_kg_costs"):
            data[field] = {}
        with self.assertRaises(mod.InputError):
            mod.calculate(data)

    def test_zero_valued_cost_categories_are_not_sufficient(self):
        data = baseline()
        data["fixed_costs"] = {"irrigation": "0"}
        data["production_variable_costs"] = {"seed": "0"}
        data["per_sold_kg_costs"] = {"transport": "0"}
        with self.assertRaises(mod.InputError):
            mod.calculate(data)

    def test_attestation_must_be_boolean(self):
        data = baseline()
        data["all_material_costs_documented"] = "true"
        with self.assertRaises(mod.InputError):
            mod.calculate(data)

    def test_negative_and_boolean_inputs_are_rejected(self):
        for value in ("-0.01", True, None):
            with self.subTest(value=value):
                data = baseline()
                data["area_hectares"] = value
                with self.assertRaises(mod.InputError):
                    mod.calculate(data)


if __name__ == "__main__":
    unittest.main()
