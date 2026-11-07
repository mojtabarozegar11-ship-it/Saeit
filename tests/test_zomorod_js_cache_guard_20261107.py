"""Offline tests for the Zomorod one-asset Cache-Control publication gate."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/zomorod_js_cache_guard_20261107.py"
SPEC = importlib.util.spec_from_file_location("zm_cache_guard", SCRIPT)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class CacheGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        root = base / "public_html"
        asset_dir = root / "static/site/zomorod-perf"
        asset_dir.mkdir(parents=True)
        home = root / "index.html"
        asset = asset_dir / guard.ASSET_NAME
        home.write_bytes(b"unchanged-approved-home")
        asset.write_bytes(b"unchanged-approved-javascript")
        values = {
            "HOME": home, "ASSET_DIR": asset_dir, "ASSET": asset,
            "CONFIG": asset_dir / ".htaccess",
            "PRIVATE_DIR": base / ".private/zomorod-js-cache-config",
            "HOME_SHA": guard.sha(home.read_bytes()),
            "JS_SHA": guard.sha(asset.read_bytes()),
        }
        for key, value in values.items():
            original = getattr(guard, key)
            setattr(guard, key, value)
            self.addCleanup(setattr, guard, key, original)

    def test_apply_preserves_home_and_asset(self):
        with patch.object(guard, "verify_public"):
            guard.apply()
        self.assertEqual(guard.CONFIG.read_bytes(), guard.CONFIG_BYTES)
        self.assertEqual(guard.sha(guard.HOME.read_bytes()), guard.HOME_SHA)
        self.assertEqual(guard.sha(guard.ASSET.read_bytes()), guard.JS_SHA)

    def test_public_verification_failure_quarantines_new_config(self):
        with patch.object(guard, "verify_public", side_effect=RuntimeError("proxy stripped header")):
            with self.assertRaisesRegex(RuntimeError, "stripped header"):
                guard.apply()
        self.assertFalse(guard.CONFIG.exists())
        self.assertEqual(len(list(guard.PRIVATE_DIR.iterdir())), 1)
        self.assertEqual(guard.sha(guard.HOME.read_bytes()), guard.HOME_SHA)

    def test_preexisting_file_cannot_be_overwritten(self):
        guard.CONFIG.write_text("other publisher\n")
        with self.assertRaisesRegex(RuntimeError, "Existing directory"):
            guard.apply()
        self.assertEqual(guard.CONFIG.read_text(), "other publisher\n")

    def test_modified_file_refuses_rollback(self):
        guard.CONFIG.write_text("other publisher\n")
        with self.assertRaisesRegex(RuntimeError, "third-party"):
            guard.quarantine_exact()
        self.assertTrue(guard.CONFIG.exists())


if __name__ == "__main__":
    unittest.main()
