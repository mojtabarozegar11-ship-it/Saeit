"""Integration tests for the private guided farm-budget entry point."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

import guided_start
from calculator import evaluate


class GuidedStartTests(unittest.TestCase):
    def user_inputs(self, *values):
        items = iter(values)
        return lambda message: next(items)

    def test_success_creates_four_consistent_reports_and_original_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            messages = []
            code = guided_start.main(
                ["--output-parent", d],
                read=self.user_inputs("USD", "1", "Orchard", "1000", "10", "4", "3000", "5", "YES"),
                write=messages.append,
            )
            self.assertEqual(code, 0)
            folder, = list(Path(d).glob("farm-budget-*"))
            data = json.loads((folder / "my_farm.json").read_text(encoding="utf-8"))
            report = json.loads((folder / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(data["enterprises"][0]["units_sold"], "1000")
            self.assertEqual(report, evaluate(data))
            self.assertEqual(report["portfolio"]["operating_profit"], "2500.00")
            self.assertIn("Farm Enterprise Economics", (folder / "management-report.html").read_text())
            with (folder / "scenarios.csv").open(newline="", encoding="utf-8") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 9)
            with (folder / "joint-stress.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 54)
            self.assertEqual({row["scope"] for row in rows}, {"enterprise", "portfolio"})
            self.assertTrue(any("Reports saved" in line for line in messages))

    def test_invalid_numbers_and_duplicate_names_are_reprompted(self):
        output = []
        data = guided_start.collect_budget(
            read=self.user_inputs(
                "____", "invalid currency!", "CAD", "0", "2",
                "Berries", "-1", "12.5", "2", "1", "10", "1",
                "berries", "Greenhouse", "1", "4", "2", "0", "0",
            ),
            write=output.append,
        )
        self.assertEqual([r["name"] for r in data["enterprises"]], ["Berries", "Greenhouse"])
        self.assertEqual(data["enterprises"][0]["units_sold"], "12.5")
        self.assertTrue(any("distinct name" in line for line in output))
        self.assertTrue(any("Please correct this number" in line for line in output))

    def test_confirmation_is_fail_closed_and_creates_no_files(self):
        with tempfile.TemporaryDirectory() as d:
            code = guided_start.main(
                ["--output-parent", d],
                read=self.user_inputs("USD", "1", "Orchard", "1", "1", "1", "1", "0", "yes"),
                write=lambda _: None,
            )
            self.assertEqual(code, 0)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_end_of_input_is_safe_cancellation(self):
        with tempfile.TemporaryDirectory() as d:
            code = guided_start.main(
                ["--output-parent", d],
                read=lambda _: (_ for _ in ()).throw(EOFError()),
                write=lambda _: None,
            )
            self.assertEqual(code, 0)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_each_export_goes_to_new_folder_without_overwrite(self):
        budget = {"currency": "USD", "enterprises": [{
            "name": "Orchard", "units_sold": "1", "unit_price": "3",
            "variable_cost_per_unit": "1", "allocated_fixed_cost": "1",
            "selling_fee_percent": "0",
        }]}
        with tempfile.TemporaryDirectory() as d:
            first = guided_start.create_private_reports(budget, d)
            second = guided_start.create_private_reports(budget, d)
            self.assertNotEqual(first, second)
            self.assertEqual((first / "results.json").read_bytes(),
                             (second / "results.json").read_bytes())

    def test_output_parent_symlink_is_rejected_before_any_writes(self):
        budget = {"currency": "USD", "enterprises": [{
            "name": "Orchard", "units_sold": "1", "unit_price": "3",
            "variable_cost_per_unit": "1", "allocated_fixed_cost": "1",
            "selling_fee_percent": "0",
        }]}
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "actual"
            target.mkdir()
            alias = Path(d) / "alias"
            alias.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                guided_start.create_private_reports(budget, alias)
            self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
