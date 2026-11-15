"""Regression test for the guarded TRON producer source closure."""
from pathlib import Path
from tempfile import TemporaryDirectory
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



    def test_in_tree_symlink_is_not_counted_as_a_safe_dependency(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in REQUIRED:
                file = root / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("# original\n", encoding="utf-8")
            self.assertEqual(missing_paths(root), [])
            alias = root / "mpw_commerce/buyer_wallets.py"
            alias.unlink()
            alias.symlink_to(root / "mpw_commerce/models.py")
            self.assertEqual(missing_paths(root), ["mpw_commerce/buyer_wallets.py"])

    def test_symlinked_parent_directory_is_rejected_even_within_root(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in REQUIRED:
                file = root / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("# original\n", encoding="utf-8")
            (root / "services").rename(root / "copied_services")
            (root / "services").symlink_to(root / "copied_services", target_is_directory=True)
            missing = missing_paths(root)
            required_service_paths = [name for name in REQUIRED if name.startswith("services/")]
            self.assertEqual(sorted(missing), sorted(required_service_paths))

    def test_missing_and_unsafe_roots_fail_closed(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "nonexistent"
            self.assertEqual(missing_paths(root), list(REQUIRED))
            real = Path(folder) / "real"
            real.mkdir()
            link = Path(folder) / "linked"
            link.symlink_to(real, target_is_directory=True)
            self.assertEqual(missing_paths(link), list(REQUIRED))

if __name__ == "__main__":
    unittest.main()
