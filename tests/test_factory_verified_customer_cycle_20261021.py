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

    def test_exact_hash_cadence_avoids_repeated_extraction_without_approving_sales(self):
        from unittest import mock
        first, fresh = customer.inspect_product_scheduled(
            self.output, self.recipe, now=1000)
        self.assertTrue(fresh)
        self.assertEqual(first["customer_zip_extract_test"], "passed")
        with mock.patch.object(customer, "inspect_product", side_effect=AssertionError("duplicate unzip")):
            same, fresh = customer.inspect_product_scheduled(
                self.output, self.recipe, now=1005)
        self.assertFalse(fresh)
        self.assertEqual(same["artifact_sha256"], first["artifact_sha256"])
        self.assertIs(same["professional_quality_1000_approved"], False)
        ticket = self.output / "quality-excellence" / "customer-extracted-review"
        ticket = ticket / self.recipe / first["source_sha256"] / "pending.json"
        self.assertIsNone(json.loads(ticket.read_text())["verified_total_score"])

    def test_cadence_expiry_or_manifest_change_reexecutes_full_zip_tests(self):
        from unittest import mock
        customer.inspect_product_scheduled(self.output, self.recipe, now=1000)
        actual = customer.inspect_product
        with mock.patch.object(customer, "inspect_product", wraps=actual) as call:
            _, full = customer.inspect_product_scheduled(self.output, self.recipe, now=3001)
        self.assertTrue(full)
        self.assertEqual(call.call_count, 1)
        manifest = self.product() / "manufacturing_manifest.json"
        data = json.loads(manifest.read_text())
        data["unrelated_revision_note"] = "new metadata, unchanged artifact"
        manifest.write_text(json.dumps(data))
        with mock.patch.object(customer, "inspect_product", wraps=actual) as call:
            _, full = customer.inspect_product_scheduled(self.output, self.recipe, now=3002)
        self.assertTrue(full)
        self.assertEqual(call.call_count, 1)

    def test_cached_cadence_rejects_corrupted_zip(self):
        customer.inspect_product_scheduled(self.output, self.recipe, now=1000)
        package = self.product() / (self.recipe + "-internal-qa.zip")
        package.write_bytes(package.read_bytes() + b"changed")
        with self.assertRaisesRegex(RuntimeError, "CUSTOMER_ZIP_HASH_MISMATCH"):
            customer.inspect_product_scheduled(self.output, self.recipe, now=1001)

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
                archive.writestr(name, mutation(name, contents), compress_type=zipfile.ZIP_DEFLATED)
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

    def test_vps_installer_copies_new_mandatory_customer_qa(self):
        # Deployment must use the same sources tested on GitHub.
        installer = (ROOT / "deploy" / "install_autonomous_factory_products.sh").read_text(encoding="utf8")
        module = "factory_verified_customer_cycle_20261021.py"
        self.assertIn('test -f "$repo/scripts/' + module + '"', installer)
        self.assertIn('test ! -L "$repo/scripts/' + module + '"', installer)
        self.assertIn("factory_vps_product_cycle.py \\\n         " + module + " \\\n", installer)
        self.assertIn('"$scripts/' + module + '"', installer)
        self.assertIn('"$python" "$scripts/factory_vps_product_cycle.py"', installer)



if __name__ == "__main__":
    unittest.main()
