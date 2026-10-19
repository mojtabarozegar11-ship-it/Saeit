"""Factory manufactures a working product without orders and without publishing."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "saeit_maker", str(ROOT / "scripts" / "factory_product_maker.py")
)
maker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maker)


class ManufacturerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.recipes = base / "recipes"
        self.product = self.recipes / "farm_enterprise_economics"
        shutil.copytree(ROOT / "product_recipes" / "farm_enterprise_economics", self.product)
        self.output = base / "private"

    def test_manufactures_real_zip_without_orders_or_api(self):
        result = maker.manufacture("farm_enterprise_economics", self.recipes, self.output)
        self.assertTrue(result["changed"])
        path = Path(result["private_artifact"])
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with zipfile.ZipFile(str(path)) as archive:
            names = archive.namelist()
            self.assertIn("farm_enterprise_economics/calculator.py", names)
            self.assertIn("farm_enterprise_economics/test_calculator.py", names)
            self.assertIn("farm_enterprise_economics/README.md", names)
            self.assertIsNone(archive.testzip())
        manifest = json.loads((path.parent / "manufacturing_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["qa_status"], "passed")
        self.assertGreaterEqual(manifest["qa_test_count"], maker.MIN_TESTS_PER_RECIPE)
        self.assertEqual(manifest["minimum_tests_required"], 1)
        self.assertEqual(manifest["quality_scope"], "software_tests_and_zip_integrity_only")
        self.assertEqual(manifest["scientific_validity"], "pending_independent_specialist_review")
        self.assertEqual(manifest["economic_value"], "pending_independent_review")
        self.assertFalse(manifest["customer_order_required"])
        self.assertFalse(manifest["public_listing_enabled"])
        self.assertIsNone(manifest["price"])

    def test_zero_discovered_tests_fails_even_when_unittest_reports_ok(self):
        completed = maker.subprocess.CompletedProcess(
            args=["python", "-m", "unittest"], returncode=0,
            stdout="", stderr="Ran 0 tests in 0.000s\\n\\nOK\\n")
        with patch.object(maker.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "executed_tests=0;minimum=1"):
                maker.verify_recipe(self.product)

    def test_same_source_skips_repeat_generation(self):
        a = maker.manufacture("farm_enterprise_economics", self.recipes, self.output)
        b = maker.manufacture("farm_enterprise_economics", self.recipes, self.output)
        self.assertTrue(a["changed"])
        self.assertFalse(b["changed"])
        self.assertEqual(a["private_artifact"], b["private_artifact"])

    def test_rejects_failing_test_without_replacing_package(self):
        before = maker.manufacture("farm_enterprise_economics", self.recipes, self.output)
        filename = Path(before["private_artifact"])
        digest = maker.sha256_file(filename)
        (self.product / "calculator.py").write_text("raise RuntimeError('broken')\n", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            maker.manufacture("farm_enterprise_economics", self.recipes, self.output)
        self.assertEqual(maker.sha256_file(filename), digest)

    def test_missing_recipe_file_rejected(self):
        (self.product / "README.md").unlink()
        with self.assertRaises(RuntimeError):
            maker.manufacture("farm_enterprise_economics", self.recipes, self.output)
        self.assertFalse(self.output.exists())

    def test_zip_is_reproducible_across_private_destinations(self):
        first = maker.manufacture("farm_enterprise_economics", self.recipes, self.output)
        second = maker.manufacture("farm_enterprise_economics", self.recipes, Path(self.tmp.name) / "another")
        self.assertEqual(
            maker.sha256_file(Path(first["private_artifact"])),
            maker.sha256_file(Path(second["private_artifact"]))
        )

    def test_new_recipe_folder_is_discovered_without_code_registration(self):
        new_recipe = self.recipes / "new_product_family"
        shutil.copytree(self.product, new_recipe)
        readme = new_recipe / "README.md"
        readme.write_text("# New Product Family\n", encoding="utf-8")
        catalog = maker.discover_recipes(self.recipes)
        self.assertEqual(set(catalog), {"farm_enterprise_economics", "new_product_family"})
        self.assertEqual(catalog["new_product_family"][0], "New Product Family")
        result = maker.manufacture("new_product_family", self.recipes, self.output)
        self.assertEqual(result["qa_status"], "passed")
        self.assertTrue(Path(result["private_artifact"]).is_file())

    def test_default_catalog_has_no_two_recipe_limit(self):
        self.assertIn("greenhouse_crop_margin", maker.RECIPES)
        self.assertGreaterEqual(len(maker.RECIPES), 3)
        self.assertEqual(maker.RECIPES["greenhouse_crop_margin"][0],
                         "Greenhouse Crop Margin and Break-even Planner")


if __name__ == "__main__":
    unittest.main()
