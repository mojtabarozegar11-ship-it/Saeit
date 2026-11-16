"""Unit tests for conditional algebra only; not empirical R01 validation."""
import unittest
from economic_break_even import calculate, FIELDS

class EconomicBreakEvenTests(unittest.TestCase):
    def setUp(self):
        self.v = dict.fromkeys(FIELDS, 0)
        self.v["crop_price_per_kg"] = 2

    def test_zero_delta(self):
        self.assertEqual(calculate(self.v)["break_even_additional_yield_kg_per_period"], 0)

    def test_water_cost(self):
        self.v.update(delta_water_m3=10, water_tariff_per_m3=3)
        self.assertEqual(calculate(self.v)["break_even_additional_yield_kg_per_period"], 15)

    def test_events_and_drainage(self):
        self.v.update(delta_events=2, event_labor_cost=4,
                      delta_drainage_mm=5, drainage_cost_per_mm=2)
        self.assertEqual(calculate(self.v)["incremental_cost_currency_per_period"], 18)

    def test_negative_cost_credit(self):
        self.v.update(delta_water_m3=-10, water_tariff_per_m3=3)
        self.assertEqual(calculate(self.v)["break_even_additional_yield_kg_per_period"], 0)

    def test_zero_price_unknown(self):
        self.v["crop_price_per_kg"] = 0
        self.assertIsNone(calculate(self.v)["break_even_additional_yield_kg_per_period"])

    def test_missing(self):
        self.v.pop("delta_events")
        with self.assertRaises(ValueError):
            calculate(self.v)

    def test_extra(self):
        self.v["invented"] = 1
        with self.assertRaises(ValueError):
            calculate(self.v)

    def test_boolean_rejected(self):
        self.v["delta_events"] = True
        with self.assertRaises(ValueError):
            calculate(self.v)

    def test_nonfinite_rejected(self):
        self.v["delta_water_m3"] = float("nan")
        with self.assertRaises(ValueError):
            calculate(self.v)

    def test_negative_price_rejected(self):
        self.v["crop_price_per_kg"] = -1
        with self.assertRaises(ValueError):
            calculate(self.v)

if __name__ == "__main__":
    unittest.main()
