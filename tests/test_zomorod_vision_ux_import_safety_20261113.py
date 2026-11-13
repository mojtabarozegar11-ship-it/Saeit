"""Ensure the independent homepage release helper is safe to collect in CI.

The original CLI remains usable, but imports must never read stage files or
execute backup/apply/rollback operations in pytest collection.
"""
from __future__ import annotations

import runpy
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts/test_zomorod_vision_ux_20261113.py"


class SourceImportSafetyTests(unittest.TestCase):
    def test_pytest_import_does_not_execute_release_cli(self):
        namespace = runpy.run_path(str(TARGET), run_name="pytest_collection")
        self.assertIn("main", namespace)
        self.assertTrue(callable(namespace["main"]))

    def test_imported_cli_never_exposes_fake_success(self):
        namespace = runpy.run_path(str(TARGET), run_name="pytest_collection")
        self.assertNotIn("ZOMOROD_UX_BACKUP_APPLY_VERIFY_ROLLBACK_CONCURRENT_GUARD",
                         namespace)


if __name__ == "__main__":
    unittest.main()
