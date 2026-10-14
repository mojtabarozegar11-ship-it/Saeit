"""Independent QA for the real offline irrigation allocation calculator."""
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest

# Avoid importing the first recipe's identically named calculator.py during
# repository-wide pytest runs. Load this recipe's module by its exact path.
spec = importlib.util.spec_from_file_location(
    "saeit_water_budget_calculator", str(Path(__file__).with_name("calculator.py")))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
evaluate = module.evaluate


def sample():
    return {"currency": "USD", "water_available_m3": 1000, "crops": [
        {"name": "Crop A", "max_area_ha": 1, "water_m3_per_ha": 1000, "gross_margin_per_ha": 2000},
        {"name": "Crop B", "max_area_ha": 1, "water_m3_per_ha": 500, "gross_margin_per_ha": 1500},
    ]}


class WaterBudgetTests(unittest.TestCase):
    def test_maximizes_fractional_margin(self):
        value = evaluate(sample())
        self.assertEqual([x["crop"] for x in value["allocations"]], ["Crop B", "Crop A"])
        self.assertEqual(Decimal(value["estimated_total_gross_margin"]), Decimal("2500"))
        self.assertEqual(Decimal(value["water_used_m3"]), Decimal("1000"))
        self.assertEqual(Decimal(value["allocations"][1]["area_allocated_ha"]), Decimal("0.5"))

    def test_respects_zero_water(self):
        data = sample()
        data["water_available_m3"] = 0
        value = evaluate(data)
        self.assertEqual(Decimal(value["water_used_m3"]), 0)
        self.assertEqual(Decimal(value["estimated_total_gross_margin"]), 0)

    def test_unused_water_is_reported(self):
        data = sample()
        data["water_available_m3"] = 5000
        value = evaluate(data)
        self.assertEqual(Decimal(value["unused_water_m3"]), 3500)

    def test_zero_margin_not_allocated(self):
        data = sample()
        data["crops"][0]["gross_margin_per_ha"] = 0
        value = evaluate(data)
        self.assertEqual(Decimal(value["water_used_m3"]), 500)

    def test_rejects_negative_budget(self):
        data = sample()
        data["water_available_m3"] = -1
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_rejects_zero_water_requirement(self):
        data = sample()
        data["crops"][0]["water_m3_per_ha"] = 0
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_rejects_duplicate_crops(self):
        data = sample()
        data["crops"][1]["name"] = "crop a"
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_rejects_nonfinite(self):
        data = sample()
        data["crops"][0]["gross_margin_per_ha"] = "NaN"
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_deterministic(self):
        self.assertEqual(evaluate(sample()), evaluate(sample()))


if __name__ == "__main__":
    unittest.main()
