"""Regression test for the guarded TRON producer source closure."""
from pathlib import Path
import unittest

from scripts.mpw_commerce_dependency_preflight_20261115 import (
    REQUIRED,
    missing_paths,
)


class CommerceSourceClosureTests(unittest.TestCase):
    def test_all_required_files_are_present_and_not_symlinks(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(missing_paths(root), [])

    def test_manifest_contains_actual_producer_and_schema(self):
        self.assertIn("services/mpw_walletless_commercial_intent.py", REQUIRED)
        self.assertIn("mpw_commerce/models.py", REQUIRED)
        self.assertIn("mpw_commerce/migrations/0002_guest_trx_delivery.py", REQUIRED)


if __name__ == "__main__":
    unittest.main()
