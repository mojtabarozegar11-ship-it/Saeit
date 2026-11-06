"""Regression: a released product must never delete through symlinked parents."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_vps_product_cycle.py"
SPEC = importlib.util.spec_from_file_location("factory_vps_product_cycle_cleanup_test", SOURCE)
FACTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FACTORY)


class SingleProductCleanupSafetyTests(unittest.TestCase):
    def test_refuses_symlink_parent_without_deleting_external_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "private"
            external = base / "other-owner"
            root.mkdir()
            (external / "farm_enterprise_economics").mkdir(parents=True)
            marker = external / "farm_enterprise_economics" / "keep.txt"
            marker.write_text("private other data", encoding="utf-8")
            (root / "research-dossiers").symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(RuntimeError, "PRODUCT_CLEANUP"):
                FACTORY._cleanup_completed_product_extras(root, "farm_enterprise_economics")

            self.assertTrue(marker.is_file())

    def test_refuses_invalid_recipe(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "PRODUCT_CLEANUP"):
                FACTORY._cleanup_completed_product_extras(Path(temporary), "../outside")

    def test_preflights_all_targets_before_any_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "private"
            external = base / "external"
            root.mkdir()
            external.mkdir()
            first = root / "generated-product-recipes" / "farm_enterprise_economics"
            first.mkdir(parents=True)
            marker = first / "keep.txt"
            marker.write_text("keep until safety is known", encoding="utf-8")
            (root / "research-dossiers").symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(RuntimeError, "PRODUCT_CLEANUP"):
                FACTORY._cleanup_completed_product_extras(root, "farm_enterprise_economics")

            self.assertTrue(marker.is_file())

    def test_valid_cleanup_preserves_accepted_product_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recipe = "farm_enterprise_economics"
            working = root / "research-dossiers" / recipe
            working.mkdir(parents=True)
            (working / "intermediate.json").write_text("{}", encoding="utf-8")
            archive = root / "digital-products" / recipe / (recipe + "-internal-qa.zip")
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"archived delivery kept")

            FACTORY._cleanup_completed_product_extras(root, recipe)

            self.assertFalse(working.exists())
            self.assertEqual(archive.read_bytes(), b"archived delivery kept")


if __name__ == "__main__":
    unittest.main()
