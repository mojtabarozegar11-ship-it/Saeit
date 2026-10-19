"""Transactional synchronization of active and retired product recipes."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = ROOT / "scripts" / "factory_recipe_catalog_sync.py"
spec = importlib.util.spec_from_file_location("recipe_catalog_sync", str(SYNC_PATH))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class RecipeCatalogSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.active = self.root / "runtime" / "product_recipes"
        self.retired = self.root / "private" / "retired-recipes"
        self.manifest = self.root / "runtime" / "installed-recipes.json"
        shutil.copytree(ROOT / "product_recipes" / "farm_enterprise_economics",
                        self.source / "farm_enterprise_economics")

    def test_replaces_stale_files_and_quarantines_removed_recipe(self):
        shutil.copytree(ROOT / "product_recipes" / "water_budget_economics",
                        self.source / "water_budget_economics")
        shutil.copytree(self.source / "farm_enterprise_economics",
                        self.active / "farm_enterprise_economics")
        (self.active / "farm_enterprise_economics" / "stale.py").write_text(
            "raise RuntimeError('stale')\\n", encoding="utf-8")
        shutil.copytree(self.source / "water_budget_economics",
                        self.active / "obsolete_recipe")
        sentinel = self.root / "private" / "digital-products" / "keep.zip"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_bytes(b"keep")
        result = sync.sync_catalog(self.source, self.active, self.retired, self.manifest)
        self.assertEqual(set(sync.maker.discover_recipes(self.active)),
                         {"farm_enterprise_economics", "water_budget_economics"})
        self.assertFalse((self.active / "farm_enterprise_economics" / "stale.py").exists())
        self.assertEqual(result["retired_recipes"], ["obsolete_recipe"])
        archives = list(self.retired.glob("obsolete_recipe-*"))
        self.assertEqual(len(archives), 1)
        self.assertTrue((archives[0] / "README.md").is_file())
        self.assertEqual(sentinel.read_bytes(), b"keep")
        installed = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(installed["active_recipes"], sorted(result["active_recipes"]))
        self.assertEqual(installed["retired_this_sync"], ["obsolete_recipe"])

    def test_zero_test_recipe_aborts_without_changing_active_catalog(self):
        (self.source / "empty_test_recipe").mkdir()
        (self.source / "empty_test_recipe" / "README.md").write_text(
            "# Empty Test Recipe\\n", encoding="utf-8")
        (self.source / "empty_test_recipe" / "test_empty.py").write_text(
            "# no test cases\\n", encoding="utf-8")
        shutil.copytree(self.source / "farm_enterprise_economics",
                        self.active / "farm_enterprise_economics")
        with self.assertRaisesRegex(RuntimeError, "executed_tests=0;minimum=1"):
            sync.sync_catalog(self.source, self.active, self.retired, self.manifest)
        self.assertIn("farm_enterprise_economics", sync.maker.discover_recipes(self.active))
        self.assertFalse(self.manifest.exists())
        self.assertFalse(list(self.retired.glob("*")))


if __name__ == "__main__":
    unittest.main()
