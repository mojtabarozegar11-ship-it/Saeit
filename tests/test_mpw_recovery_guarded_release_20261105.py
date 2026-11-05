"""File-only release/rollback tests in temporary directories; no cPanel/DB."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mpw_recovery_release_guarded",
    SOURCE / "scripts/mpw_recovery_guarded_release_20261105.py",
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class GuardedRecoveryReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mpw-recovery-release-isolated-")
        root = Path(self.tmp.name)
        self.app = root / "app"
        self.stage = root / "stage"
        self.backups = root / "backup"
        for rel in release.FILES.values():
            (self.app / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.stage / rel).parent.mkdir(parents=True, exist_ok=True)
        self.fake = {
            "guest": b'def patch_public(namespace): pass\ndef patch_commercial(namespace): pass\n',
            "models": b'class Order: pass\nclass PaymentIntent: pass\n',
            "settings": b'DEFAULT_FROM_EMAIL = "test@invalid.example"\n# env.bool available\n',
        }
        self.fake["models"] = (
            b'class Order(object): pass\nclass PaymentIntent(object): pass\n'
        )
        for name in ("guest", "models", "settings"):
            (self.app / release.FILES[name]).write_bytes(self.fake[name])
        for name in release.SOURCE_DIGESTS:
            (self.stage / release.FILES[name]).write_bytes(
                (SOURCE / release.FILES[name]).read_bytes()
            )
        self.patches = [
            patch.object(release, "APP", self.app),
            patch.object(release, "BACKUPS", self.backups),
            patch.object(release, "EXPECTED_GUEST_BASE", release.digest(self.fake["guest"])),
            patch.object(release, "guard_host"),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def test_preflight_is_pure_and_builds_expected_changes(self):
        old, new = release.build_plan(self.stage)
        self.assertEqual(len(old), 7)
        self.assertEqual(len(new), 7)
        self.assertEqual(new["guest"], (SOURCE / release.FILES["guest"]).read_bytes())
        self.assertIn(b"MPW_GUEST_RECOVERY_ENABLED = False", new["settings"])
        self.assertIn(b"MPW_RECOVERY01_MODELS_20261105", new["models"])
        self.assertFalse((self.app / release.FILES["migration"]).exists())
        self.assertEqual((self.app / release.FILES["models"]).read_bytes(), self.fake["models"])

    def test_unreviewed_payload_fails_closed_without_writing_app(self):
        path = self.stage / release.FILES["recovery"]
        path.write_bytes(path.read_bytes() + b"\n# arbitrary code drift\n")
        with self.assertRaisesRegex(RuntimeError, "UNREVIEWED_SOURCE"):
            release.build_plan(self.stage)
        self.assertFalse((self.app / release.FILES["recovery"]).exists())

    def test_concurrent_edit_cannot_be_overwritten(self):
        path = self.app / release.FILES["models"]
        digest = release.digest(path.read_bytes())
        path.write_bytes(path.read_bytes() + b"\n# concurrent admin change\n")
        with self.assertRaisesRegex(RuntimeError, "CONCURRENT_FILE_EDIT"):
            release._atomic(path, b"modified", expected=digest)
        self.assertIn(b"concurrent admin change", path.read_bytes())

    def test_staged_publish_then_exact_source_rollback(self):
        verified = {"vendor": "mysql", "m39": True, "m40": True,
                    "tables": ["core_guestorderemail", "core_guestrecoverytoken",
                               "core_guestrecoveryrate"],
                    "enabled": False, "mail": False}
        run = "202611050042"
        with patch.object(release, "require_before_schema", return_value=True), \
             patch.object(release, "migrate_new_tables"), \
             patch.object(release, "db_state", return_value=verified), \
             patch.object(release, "restart") as restarted:
            release.publish(self.stage, run)
            self.assertEqual(restarted.call_count, 1)
            self.assertTrue((self.app / release.FILES["migration"]).is_file())
            self.assertIn(b"MPW_GUEST_RECOVERY_EMAIL_APPROVED = False",
                          (self.app / release.FILES["settings"]).read_bytes())
            release.rollback(run)
            self.assertEqual(restarted.call_count, 2)
        for key in self.fake:
            self.assertEqual((self.app / release.FILES[key]).read_bytes(), self.fake[key])
        for key in release.NEW_FILES:
            self.assertFalse((self.app / release.FILES[key]).exists())
        self.assertTrue((self.backups / run / "manifest.json").is_file())

    def test_rollback_rejects_newer_changes(self):
        verified = {"vendor": "mysql", "m39": True, "m40": True,
                    "tables": ["a", "b", "c"], "enabled": False, "mail": False}
        run = "202611050043"
        with patch.object(release, "require_before_schema", return_value=True), \
             patch.object(release, "migrate_new_tables"), \
             patch.object(release, "db_state", return_value=verified), \
             patch.object(release, "restart"):
            release.publish(self.stage, run)
            path = self.app / release.FILES["settings"]
            path.write_bytes(path.read_bytes() + b"\n# newer live edit\n")
            with self.assertRaisesRegex(RuntimeError, "ROLLBACK_SOURCE_DRIFT"):
                release.rollback(run)
            self.assertIn(b"newer live edit", path.read_bytes())

    def test_schema_drift_blocks_publish_before_any_write(self):
        invalid = {"vendor": "mysql", "m39": False, "m40": False,
                   "tables": [], "enabled": False, "mail": False}
        with patch.object(release, "db_state", return_value=invalid):
            with self.assertRaisesRegex(RuntimeError, "MIGRATION_BASELINE_DRIFT"):
                release.require_before_schema()
        self.assertFalse((self.app / release.FILES["migration"]).exists())

    def test_migration_failure_restores_original_code_without_dropping_tables(self):
        run = "202611050044"
        with patch.object(release, "require_before_schema", return_value=True), \
             patch.object(release, "migrate_new_tables", side_effect=RuntimeError("synthetic migration failure")), \
             patch.object(release, "restart") as restarted:
            with self.assertRaisesRegex(RuntimeError, "synthetic migration failure"):
                release.publish(self.stage, run)
            self.assertEqual(restarted.call_count, 1)
        for name in self.fake:
            self.assertEqual((self.app / release.FILES[name]).read_bytes(), self.fake[name])
        for name in release.NEW_FILES:
            self.assertFalse((self.app / release.FILES[name]).exists())
        self.assertTrue((self.backups / run / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
