"""Real-package F28 build, customer smoke, failure and bounded repair tests."""
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "f28_cycle", str(ROOT / "scripts" / "factory_f28_private_build_cycle_20261021.py"))
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


class F28PrivateCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "recipes" / "greenhouse_crop_margin"
        shutil.copytree(ROOT / "product_recipes" / "greenhouse_crop_margin", self.source)
        self.makers = self.base / "scripts"
        self.makers.mkdir()
        for name in ("factory_product_maker.py",
                     "factory_personal_owner_passport_policy_20261020.py"):
            shutil.copy2(ROOT / "scripts" / name, self.makers / name)
        self.maker = self.makers / "factory_product_maker.py"
        self.private = self.base / "private"

    def build(self):
        return cycle.build_cycle(self.source, self.maker, self.private,
                                 revision="unit-test-source-sha")

    def test_actual_customer_zip_is_built_and_independently_executed(self):
        receipt = self.build()
        self.assertEqual(receipt["status"], "private_technical_candidate_verified")
        self.assertGreaterEqual(receipt["technical_tests"], 10)
        self.assertEqual(receipt["independent_black_box_checks"]["customer_scenarios_verified"], 2)
        self.assertTrue(receipt["independent_black_box_checks"]["customer_cli_from_extracted_zip"])
        self.assertFalse(receipt["independent_professional_quality_1000_passed"])
        self.assertFalse(receipt["commercial_release_authorized"])
        stock = self.private / "private-stock" / "greenhouse_crop_margin"
        archive = stock / "greenhouse_crop_margin-internal-qa.zip"
        manifest = json.loads((stock / "manufacturing_manifest.json").read_text(encoding="utf8"))
        self.assertEqual(cycle.digest(archive), manifest["artifact_sha256"])
        self.assertTrue((stock / "professional_quality_release_stop.json").is_file())
        self.assertEqual(cycle.verify_customer_package(archive, manifest)["customer_scenarios_verified"], 2)

    def test_corrupted_real_zip_is_restored_and_retested(self):
        first = self.build()
        self.assertEqual(first["status"], "private_technical_candidate_verified")
        archive = (self.private / "private-stock" / "greenhouse_crop_margin"
                   / "greenhouse_crop_margin-internal-qa.zip")
        correct = cycle.digest(archive)
        archive.write_bytes(b"deliberately-corrupted-private-test-package")
        self.assertNotEqual(cycle.digest(archive), correct)
        second = self.build()
        self.assertEqual(second["status"], "private_technical_candidate_verified")
        self.assertTrue(second["mechanical_repair_performed"])
        self.assertEqual(cycle.digest(archive), correct)
        self.assertEqual(json.loads((self.private / "private-rework-order.json")
                                    .read_text(encoding="utf8"))["status"],
                         "technical_mechanical_repair_verified")

    def test_real_source_regression_is_blocked_and_workordered(self):
        testfile = self.source / "test_calculator.py"
        with testfile.open("a", encoding="utf8") as stream:
            stream.write("\nclass BrokenEconomicModelTest(unittest.TestCase):\n"
                         "    def test_forced_bad_model(self):\n"
                         "        self.assertEqual(1, 2)\n")
        failed = self.build()
        self.assertEqual(failed["status"], "blocked_rework_required")
        order = json.loads((self.private / "private-rework-order.json").read_text(encoding="utf8"))
        self.assertEqual(order["status"], "source_or_delivery_rework_required")
        self.assertFalse(order["commercial_release_authorized"])
        self.assertFalse((self.private / "private-stock" / "greenhouse_crop_margin"
                          / "greenhouse_crop_margin-internal-qa.zip").exists())

    def test_separate_arithmetic_oracle_rejects_loss_making_price(self):
        inputs = {"area_m2":1000, "expected_yield_kg_per_m2":12,
                  "price_per_kg":2.5, "variable_cost_per_m2":15,
                  "fixed_cost_total":5000, "rejection_rate_percent":10}
        report = {"market_data_independently_validated":False,
                  "results":{"sales_revenue":"27000.00", "total_cost":"20000.00",
                             "net_margin":"7000.00", "break_even_price_per_kg":"1.85",
                             "minimum_gross_yield_kg_per_m2_to_break_even":"8.889"}}
        with self.assertRaisesRegex(cycle.TechnicalDefect, "loss"):
            cycle.validate_output(report, inputs)
        report["results"]["break_even_price_per_kg"] = "1.86"
        cycle.validate_output(report, inputs)


if __name__ == "__main__":
    unittest.main()
