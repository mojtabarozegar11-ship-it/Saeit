"""Pure stdlib safety tests for MojPlayWin recovery source inventory."""
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_recovery_dependency_preflight_20261107 import (
    MAX_SOURCE_BYTES, REQUIRED, _app_registered, inspect,
)


class SourcePreflightSafetyTests(unittest.TestCase):
    def test_app_registration_requires_unconditional_literal(self):
        self.assertTrue(_app_registered('INSTALLED_APPS = ["core", "mpw_commerce"]'))
        self.assertTrue(_app_registered('INSTALLED_APPS = []\nINSTALLED_APPS.append("mpw_commerce")'))
        self.assertFalse(_app_registered('INSTALLED_APPS = ["mpw_commerce"] if False else []'))
        self.assertFalse(_app_registered('if False:\n    INSTALLED_APPS.append("mpw_commerce")'))
        self.assertFalse(_app_registered('INSTALLED_APPS = get_apps() + ["mpw_commerce"]'))

    def test_symlinked_ancestor_cannot_be_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "app"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "mpw_trx_email_recovery.py").write_text("do-not-follow", encoding="utf-8")
            (root / "services").symlink_to(outside, target_is_directory=True)
            report = inspect(root)
            entry = next(x for x in report["inventory"]
                         if x["path"] == "services/mpw_trx_email_recovery.py")
            self.assertFalse(entry["present"])
            self.assertEqual(entry["issue"], "symlink")
            self.assertNotIn("sha256", entry)
            self.assertFalse(report["source_floor_pass"])

    def test_oversized_source_is_rejected_without_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "services/mpw_trx_email_recovery.py"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
            entry = next(x for x in inspect(root)["inventory"]
                         if x["path"] == "services/mpw_trx_email_recovery.py")
            self.assertFalse(entry["present"])
            self.assertEqual(entry["issue"], "too_large")
            self.assertNotIn("sha256", entry)

    def test_complete_synthetic_sources_never_authorize_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in REQUIRED:
                source = root / relative
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("# synthetic\n", encoding="utf-8")
            settings = root / "config/settings.py"
            settings.parent.mkdir(parents=True)
            settings.write_text('INSTALLED_APPS = ["core", "mpw_commerce"]\n',
                                encoding="utf-8")
            report = inspect(root)
            self.assertEqual(report["present_count"], len(REQUIRED))
            self.assertTrue(report["source_floor_pass"])
            self.assertFalse(report["production_runtime_verified"])
            self.assertFalse(report["release_permitted"])


if __name__ == "__main__":
    unittest.main()
