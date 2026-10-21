"""Full-package customer-side execution tests: not a professional score."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from scripts import factory_product_maker as maker
from scripts import factory_verified_customer_cycle_20261021 as customer

ROOT = Path(__file__).resolve().parents[1]


class ExtractedCustomerQATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory-customer-real-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipes = self.root / "recipes"
        self.output = self.root / "factory"
        self.recipe = "farm_enterprise_economics"
        shutil.copytree(ROOT / "product_recipes" / self.recipe, self.recipes / self.recipe)
        maker.manufacture(self.recipe, self.recipes, self.output / "digital-products")

    def product(self):
        return self.output / "digital-products" / self.recipe

    def test_real_customer_extract_and_uncertified_1000_ticket(self):
        receipt = customer.inspect_product(self.product(), self.recipe)
        self.assertEqual(receipt["customer_zip_extract_test"], "passed")
        self.assertGreaterEqual(receipt["customer_archive_tests_run"], 1)
        customer.persist_pending(self.output, receipt)
        customer.persist_pending(self.output, receipt)
        ticket = self.output / "quality-excellence" / "customer-extracted-review" / self.recipe
        ticket = ticket / receipt["source_sha256"] / "pending.json"
        doc = json.loads(ticket.read_text())
        self.assertEqual(doc["rubric_maximum"], 1000)
        self.assertIsNone(doc["verified_total_score"])
        self.assertFalse(doc["commercial_release"])
        self.assertTrue(all(x["verified_score"] is None for x in doc["rubric"].values()))

    def test_changed_zip_hash_blocks_without_rework_approval(self):
        file = self.product() / (self.recipe + "-internal-qa.zip")
        file.write_bytes(file.read_bytes() + b"bad")
        with self.assertRaisesRegex(RuntimeError, "HASH_MISMATCH"):
            customer.inspect_product(self.product(), self.recipe)

    def rewrite_archive(self, mutation):
        file = self.product() / (self.recipe + "-internal-qa.zip")
        with zipfile.ZipFile(file) as old:
            members = [(info.filename, old.read(info)) for info in old.infolist()]
        with zipfile.ZipFile(file, "w") as archive:
            for name, contents in members:
                archive.writestr(name, mutation(name, contents), compression=zipfile.ZIP_DEFLATED)
        manifest_file = self.product() / "manufacturing_manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["artifact_sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
        manifest_file.write_text(json.dumps(manifest))

    def test_technical_manifest_pass_cannot_hide_broken_customer_code(self):
        def corrupt(name, contents):
            if name.endswith("/calculator.py"):
                return b"this is invalid python @@@\n"
            return contents
        self.rewrite_archive(corrupt)
        with self.assertRaisesRegex(RuntimeError, "EXTRACTED_TESTS_FAILED"):
            customer.inspect_product(self.product(), self.recipe)

    def test_technical_manifest_pass_cannot_hide_skipped_customer_tests(self):
        def skipped(name, contents):
            if name.endswith("/test_calculator.py"):
                return b"import unittest\nclass MyTests(unittest.TestCase):\n @unittest.skip('unrun')\n def test_unrun(self): pass\n"
            return contents
        self.rewrite_archive(skipped)
        with self.assertRaisesRegex(RuntimeError, "EXTRACTED_TESTS_FAILED"):
            customer.inspect_product(self.product(), self.recipe)

    def test_two_other_real_product_families(self):
        for recipe in ("greenhouse_crop_margin", "water_budget_economics"):
            with self.subTest(recipe=recipe):
                shutil.copytree(ROOT / "product_recipes" / recipe, self.recipes / recipe)
                maker.manufacture(recipe, self.recipes, self.output / "digital-products")
                result = customer.inspect_product(
                    self.output / "digital-products" / recipe, recipe)
                self.assertEqual(result["customer_zip_extract_test"], "passed")


if __name__ == "__main__":
    unittest.main()
