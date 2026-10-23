"""Evidence-backed, offline tests for the private three-recipe source upgrade pilot."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "factory_three_private_upgrade_pilot_20261023.py"
spec = importlib.util.spec_from_file_location("factory_private_source_upgrade", str(MODULE))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
RECIPE = pilot.RECIPES[0]
COMMIT = "a" * 40


class GenuineSourceUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        root = Path(self.sandbox.name)
        self.stage = root / "stage"
        self.private = root / "private"
        self.private.mkdir()
        (self.stage / "scripts").mkdir(parents=True)
        for script in ("factory_product_maker.py", "factory_personal_owner_passport_policy_20261020.py"):
            shutil.copyfile(ROOT / "scripts" / script, self.stage / "scripts" / script)
        source = self.stage / "product_recipes" / RECIPE
        source.mkdir(parents=True)
        (source / "README.md").write_text("# Private economic upgrade test\n", encoding="utf-8")
        (source / "calculator.py").write_text("def compute():\n    return 1\n", encoding="utf-8")
        (source / "test_calculator.py").write_text(
            "import unittest\nfrom calculator import compute\n"
            "class Tests(unittest.TestCase):\n"
            "    def test_function(self):\n"
            "        self.assertEqual(compute(), 1)\n", encoding="utf-8",
        )
        self.maker = pilot.load_maker(self.stage)
        self.maker.manufacture(RECIPE, self.stage / "product_recipes",
                               self.private / "digital-products")
        self.stock = self.private / "digital-products" / RECIPE
        self.stock_archive = self.stock / (RECIPE + "-internal-qa.zip")
        self.old_stock_sha = self.maker.sha256_file(self.stock_archive)
        self.source = source

    def upgrade_code_and_tests(self):
        (self.source / "calculator.py").write_text(
            "def compute():\n    return 2\n", encoding="utf-8")
        (self.source / "test_calculator.py").write_text(
            "import unittest\nfrom calculator import compute\n"
            "class Tests(unittest.TestCase):\n"
            "    def test_function(self):\n"
            "        self.assertEqual(compute(), 2)\n", encoding="utf-8",
        )

    def test_real_candidate_rebuild_is_hash_bound_and_noncommercial(self):
        self.upgrade_code_and_tests()
        receipt = pilot.upgrade_one(
            RECIPE, self.stage / "product_recipes", self.private, COMMIT, self.maker)
        self.assertNotEqual(receipt["prior_calculator_sha256"], receipt["new_calculator_sha256"])
        self.assertNotEqual(receipt["prior_artifact_sha256"], receipt["new_artifact_sha256"])
        self.assertGreaterEqual(receipt["measured_successful_tests"], 1)
        self.assertFalse(receipt["commercial_publication_allowed"])
        self.assertFalse(receipt["independent_specialist_qualification_verified"])
        self.assertIsNone(receipt["professional_1000_quality_grade"])
        self.assertEqual(self.old_stock_sha, self.maker.sha256_file(self.stock_archive))
        staged = self.private / "quality-excellence/source-upgrade-pilot-v1" / COMMIT / RECIPE
        with zipfile.ZipFile(staged / (RECIPE + "-internal-qa.zip")) as package:
            self.assertIn("return 2", package.read(RECIPE + "/calculator.py").decode())
        self.assertEqual(
            json.loads((staged / "source_upgrade_receipt.json").read_text()),
            receipt)
        again = pilot.upgrade_one(
            RECIPE, self.stage / "product_recipes", self.private, COMMIT, self.maker)
        self.assertEqual(receipt, again)

    def test_changed_tests_without_changed_executable_do_not_pass(self):
        (self.source / "README.md").write_text("# Changed heading only\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "EXECUTABLE_CODE_NOT_UPGRADED"):
            pilot.upgrade_one(RECIPE, self.stage / "product_recipes",
                              self.private, COMMIT, self.maker)

    def test_failing_new_recipe_tests_do_not_become_candidates(self):
        (self.source / "calculator.py").write_text("def compute():\n    return 2\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "PRODUCT_QA_FAILED"):
            pilot.upgrade_one(RECIPE, self.stage / "product_recipes",
                              self.private, COMMIT, self.maker)

    def test_prior_archive_tamper_is_rejected(self):
        self.upgrade_code_and_tests()
        with self.stock_archive.open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "PRIOR_QA_PROVENANCE"):
            pilot.upgrade_one(RECIPE, self.stage / "product_recipes",
                              self.private, COMMIT, self.maker)

    def test_invalid_git_sha_is_rejected_before_build(self):
        with self.assertRaisesRegex(RuntimeError, "INVALID_GIT_COMMIT"):
            pilot.run(self.stage, self.private, "wrong")


if __name__ == "__main__":
    unittest.main()
