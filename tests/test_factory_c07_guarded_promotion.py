"""No-network proof of safe F01 source+warehouse promotion and fail-closed preflight."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from scripts import factory_c07_guarded_promotion as c07
from scripts import factory_product_maker as maker


HERE = Path(__file__).resolve().parents[1]
NAME = "farm_enterprise_economics"
SOURCE = HERE / "product_recipes" / NAME


class GuardedPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="c07-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name) / "factory-runtime"
        ops = self.base / "operations"
        self.stage = ops / "f01-c06-private-stage-test"
        self.runtime = ops / "single-product-runtime"
        self.private = self.base / "private/autonomous-product-cycle"
        (ops / "backups").mkdir(parents=True)
        (self.runtime / "product_recipes").mkdir(parents=True)
        (self.private / "digital-products").mkdir(parents=True)
        (self.private / "quality-excellence/product-flow/active-slots").mkdir(parents=True)
        (self.stage / "scripts").mkdir(parents=True)
        for filename in ("factory_product_maker.py", "factory_personal_owner_passport_policy_20261020.py",
                         "factory_verified_customer_cycle_20261021.py"):
            shutil.copy2(HERE / "scripts" / filename, self.stage / "scripts" / filename)
        self.old_source = self.runtime / "product_recipes" / NAME
        self.old_source.mkdir()
        for filename in ("README.md", "calculator.py", "example_inputs.json", "test_calculator.py"):
            shutil.copy2(SOURCE / filename, self.old_source / filename)
        new = self.stage / "product_recipes" / NAME
        shutil.copytree(SOURCE, new)
        maker.manufacture(NAME, self.runtime / "product_recipes", self.private / "digital-products")
        maker.manufacture(NAME, self.stage / "product_recipes", self.stage / "private-digital-products")
        _,files = maker.inspect_recipe(self.old_source)
        self.old_sha = maker.source_digest(self.old_source, files)
        self.old_zip = json.loads((self.private / "digital-products" / NAME / "manufacturing_manifest.json").read_text())["artifact_sha256"]
        _,files = maker.inspect_recipe(new)
        self.new_sha = maker.source_digest(new, files)
        self.new_zip = json.loads((self.stage / "private-digital-products" / NAME / "manufacturing_manifest.json").read_text())["artifact_sha256"]
        slot = {"line_id": 41, "capacity": 1, "active": [], "waiting": [],
                "technical_exited": {NAME: {"source_sha256": self.old_sha,
                                             "artifact_sha256": self.old_zip}}}
        state = {"active_product_slot_recipes": [], "publishable_product_count": 0,
                 "commercial_quality_review_completed": False}
        (self.private / "quality-excellence/product-flow/active-slots/current.json").write_text(json.dumps(slot))
        (self.private / "production-state.json").write_text(json.dumps(state))
        (self.runtime / "run-single-product-cycle.sh").write_text(
            "#!/bin/bash\nexec 9>\".single-product-cycle.lock\"\n")
        for key,val in (("OLD_SOURCE",self.old_sha),("OLD_ARCHIVE",self.old_zip),
                        ("NEW_SOURCE",self.new_sha),("NEW_ARCHIVE",self.new_zip)):
            patch = mock.patch.object(c07,key,val)
            patch.start()
            self.addCleanup(patch.stop)

    def test_promotion_preserves_complete_old_artifact_and_state(self):
        result = c07.promote(self.base, self.stage, "a" * 40)
        self.assertEqual(result["live_source_sha256"], self.new_sha)
        self.assertFalse(result["commercial_release"])
        folder = self.base / "operations/backups" / ("f01-c07-promotion-" + "a" * 40)
        self.assertTrue((folder / "previous-source" / "calculator.py").is_file())
        self.assertTrue((folder / "previous-product" / "manufacturing_manifest.json").is_file())
        self.assertTrue((folder / "previous-product" / "professional_quality_release_stop.json").is_file())
        self.assertTrue((folder / "promotion-receipt.json").is_file())
        self.assertTrue((folder / "slots.before.json").is_file())
        self.assertEqual(c07.source_sha(maker,self.old_source,8),self.new_sha)
        self.assertTrue((self.stage / "private-digital-products" / NAME).is_dir())

    def test_stale_live_source_refuses_changes(self):
        (self.old_source / "README.md").write_text("modified without audit")
        with self.assertRaisesRegex(RuntimeError,"CURRENT_SOURCE_CONFLICT"):
            c07.promote(self.base,self.stage,"b" * 40)
        self.assertTrue((self.old_source / "test_calculator.py").is_file())
        self.assertEqual(c07.archive_sha(self.private / "digital-products" / NAME / (NAME + "-internal-qa.zip")),self.old_zip)

    def test_interrupted_swap_restores_previous_source_and_product(self):
        original_rename = Path.rename

        def fail_first_new_source(path, destination):
            if path.name == NAME and "prepared-source" in path.parts:
                raise OSError("simulated rename failure")
            return original_rename(path, destination)

        with mock.patch.object(Path, "rename", fail_first_new_source):
            with self.assertRaisesRegex(OSError, "simulated rename failure"):
                c07.promote(self.base, self.stage, "c" * 40)
        self.assertEqual(c07.source_sha(maker,self.old_source,4),self.old_sha)
        product = self.private / "digital-products" / NAME
        self.assertEqual(c07.archive_sha(product / (NAME + "-internal-qa.zip")),self.old_zip)


if __name__ == "__main__":
    unittest.main()
