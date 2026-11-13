"""Pure-stdlib source closure checks; never authorize a production release."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from scripts.mpw_recovery_dependency_preflight_20261107 import inspect


ROOT = Path(__file__).resolve().parents[1]


class MojPlayWinSourceClosureTests(unittest.TestCase):
    def test_all_known_recovery_sources_present_and_app_registered(self):
        report = inspect(ROOT)
        self.assertEqual((report["present_count"], report["required_count"]), (27, 27))
        self.assertTrue(report["mpw_commerce_registered_in_settings_source"])
        self.assertTrue(report["source_floor_pass"])
        self.assertFalse(report["release_permitted"])
        self.assertFalse(report["database_schema_verified"])
        self.assertFalse(report["production_runtime_verified"])

    def test_imported_commerce_symbols_are_defined_in_this_source_bundle(self):
        checked = 0
        for source in list((ROOT / "mpw_commerce").glob("*.py")) + list(
            (ROOT / "services").glob("mpw_*.py")
        ):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if not node.module.startswith(("services.mpw_", "mpw_commerce.")):
                    continue
                target = ROOT.joinpath(*node.module.split(".")).with_suffix(".py")
                self.assertTrue(target.is_file(), (source.name, node.module))
                imported_tree = ast.parse(target.read_text(encoding="utf-8"))
                defined = {
                    item.name for item in imported_tree.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                }
                for item in imported_tree.body:
                    if isinstance(item, ast.Assign):
                        defined.update(
                            target.id for target in item.targets
                            if isinstance(target, ast.Name)
                        )
                    elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        defined.add(item.target.id)
                    elif isinstance(item, ast.ImportFrom):
                        defined.update(alias.asname or alias.name for alias in item.names)
                for imported in node.names:
                    checked += 1
                    self.assertIn(imported.name, defined, (source.name, node.module))
        self.assertGreaterEqual(checked, 80)

    def test_isolated_payment_bridge_imports_the_existing_private_file_resolver(self):
        source = (ROOT / "services/mpw_walletless_django_test_bridge.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("from mpw_commerce.downloads import _private_file", source)
        self.assertNotIn("from mpw_commerce.fulfillment import _private_file", source)


if __name__ == "__main__":
    unittest.main()
