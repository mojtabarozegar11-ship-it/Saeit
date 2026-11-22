"""Deterministic algebra-only regression tests; no field observations."""
import unittest
from research.r01.economic_break_even import FIELDS, calculate


def baseline(**updates):
    record = {key: 0 for key in FIELDS}
    record.update(updates)
    return record


class BreakEvenBoundaryTests(unittest.TestCase):
    def test_zero_price_zero_cost_needs_no_extra_yield(self):
        result = calculate(baseline())
        self.assertTrue(result["break_even_identifiable"])
        self.assertEqual(result["break_even_additional_yield_kg_per_period"], 0)

    def test_zero_price_negative_cost_needs_no_extra_yield(self):
        result = calculate(baseline(delta_water_m3=-5, water_tariff_per_m3=2))
        self.assertTrue(result["break_even_identifiable"])
        self.assertEqual(result["incremental_margin_at_zero_yield_currency_per_period"], 10)

    def test_zero_price_positive_cost_unreachable(self):
        result = calculate(baseline(delta_water_m3=5, water_tariff_per_m3=2))
        self.assertFalse(result["break_even_identifiable"])
        self.assertTrue(result["break_even_unreachable_at_zero_crop_price"])
        self.assertIsNone(result["break_even_additional_yield_kg_per_period"])

    def test_positive_price_positive_cost(self):
        result = calculate(baseline(delta_water_m3=6, water_tariff_per_m3=2, crop_price_per_kg=3))
        self.assertEqual(result["break_even_additional_yield_kg_per_period"], 4)

    def test_positive_price_negative_cost(self):
        result = calculate(baseline(delta_water_m3=-6, water_tariff_per_m3=2, crop_price_per_kg=3))
        self.assertEqual(result["break_even_additional_yield_kg_per_period"], 0)

    def test_cost_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "incremental cost overflow"):
            calculate(baseline(delta_water_m3=1e308, water_tariff_per_m3=1e308))

    def test_yield_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "break-even yield overflow"):
            calculate(baseline(delta_water_m3=1e308, water_tariff_per_m3=1, crop_price_per_kg=1e-308))

    def test_boolean_price_rejected(self):
        with self.assertRaises(ValueError):
            calculate(baseline(crop_price_per_kg=True))

    def test_negative_price_rejected(self):
        with self.assertRaises(ValueError):
            calculate(baseline(crop_price_per_kg=-1))

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            calculate(dict(baseline(), claimed_field_observation=1))


if __name__ == "__main__":
    unittest.main()
