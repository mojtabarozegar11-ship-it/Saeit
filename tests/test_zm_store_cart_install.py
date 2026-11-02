"""Isolated release/rollback tests: never contact hosting or production DB."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/zm_store_cart_hold_guarded_install.py"
SOURCE = ROOT / "content/zomorod-v11/store_cart_index.php"
spec = importlib.util.spec_from_file_location("cart_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipUnless(shutil.which("php"), "PHP CLI required")
class CartReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "public_html/store").mkdir(parents=True)
        (self.home / ".private/zomorod-business").mkdir(parents=True)
        (self.home / "public_html/store/index.php").write_text("<?php echo 'store';")
        self.sha = module.digest(SOURCE)
        self.run = "41397698443"

    def tearDown(self):
        self.tmp.cleanup()

    def test_readonly_preflight_has_no_cart_or_lock_side_effect(self):
        module.preflight(self.home, SOURCE, self.run, self.sha)
        self.assertFalse((self.home / "public_html/store/cart").exists())
        self.assertFalse((self.home / ".private/zomorod-business/.zm-cart-hold-install.lock").exists())

    def test_install_is_additive_and_rollback_removes_only_owned_route(self):
        before = (self.home / "public_html/store/index.php").read_bytes()
        data = module.install(self.home, SOURCE, self.run, self.sha, production=False)
        self.assertFalse(data["payment_enabled"])
        target = self.home / "public_html/store/cart/index.php"
        self.assertEqual(module.digest(target), self.sha)
        self.assertEqual((self.home / "public_html/store/index.php").read_bytes(), before)
        self.assertTrue(module.rollback(self.home, self.run, production=False))
        self.assertFalse(target.parent.exists())
        self.assertEqual((self.home / "public_html/store/index.php").read_bytes(), before)

    def test_existing_cart_is_never_overwritten(self):
        target = self.home / "public_html/store/cart"
        target.mkdir()
        (target / "index.php").write_text("existing cart")
        with self.assertRaisesRegex(RuntimeError, "EXISTING_CART"):
            module.install(self.home, SOURCE, self.run, self.sha, production=False)
        self.assertEqual((target / "index.php").read_text(), "existing cart")

    def test_tampered_release_refuses_destructive_rollback(self):
        module.install(self.home, SOURCE, self.run, self.sha, production=False)
        target = self.home / "public_html/store/cart/index.php"
        target.write_text("changed by another actor")
        with self.assertRaisesRegex(RuntimeError, "ROLLBACK_OWNERSHIP_OR_HASH_MISMATCH"):
            module.rollback(self.home, self.run, production=False)
        self.assertEqual(target.read_text(), "changed by another actor")

    def test_invalid_sha_and_symlink_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "CANDIDATE_DIGEST_MISMATCH"):
            module.preflight(self.home, SOURCE, self.run, "0" * 64)
        link = self.home / "public_html/store/cart"
        link.symlink_to(self.home / ".private", target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "EXISTING_CART"):
            module.preflight(self.home, SOURCE, self.run, self.sha)

    def test_production_guard_rejects_fixture_root(self):
        with self.assertRaisesRegex(RuntimeError, "PRODUCTION_HOME_MISMATCH"):
            module.install(self.home, SOURCE, self.run, self.sha)


if __name__ == "__main__":
    unittest.main()
