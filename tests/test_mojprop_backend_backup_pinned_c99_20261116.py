"""Offline regression tests for production Moj Prop backend backup integrity.

No database, network, mail, payment, GitHub Actions or production files touched.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer


class BackendBackupIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.live = base / "live"
        self.live.mkdir()
        self.backups = base / "backups"
        self.backups.mkdir()
        self.backup = self.backups / "123"
        self.backup.mkdir()
        self.relatives = (Path("core/models.py"), Path("core/admin.py"))
        for rel in self.relatives:
            (self.live / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.live / rel).write_bytes(b"CURRENT")
            (self.backup / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.backup / rel).write_bytes(b"ORIGINAL")
        self.manifest = {
            "run_id": "123",
            "commit": "a" * 40,
            "files": [str(rel) for rel in self.relatives],
            "schema_migration_attempted": False,
        }
        for rel in self.relatives:
            self.manifest[str(rel)] = {
                "existed": True,
                "sha256": hashlib.sha256(b"ORIGINAL").hexdigest(),
                "mode": 0o640,
            }
        self.save_manifest()
        for name, value in (
            ("ROOT", self.live),
            ("BACKUP_ROOT", self.backups),
            ("ALL_FILES", self.relatives),
        ):
            patcher = patch.object(installer, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        restart = patch.object(installer, "restart_passenger")
        self.restart_mock = restart.start()
        self.addCleanup(restart.stop)

    def save_manifest(self):
        (self.backup / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )

    def test_verified_manifest_restores_both_files(self):
        self.assertEqual(installer.verify_backup_manifest(self.backup)["run_id"], "123")
        installer.restore(self.backup)
        for rel in self.relatives:
            self.assertEqual((self.live / rel).read_bytes(), b"ORIGINAL")
        self.restart_mock.assert_called_once()

    def test_started_migration_phase_blocks_explicit_rollback_before_file_writes(self):
        installer.mark_schema_migration_started(self.backup)
        self.assertIs(
            installer.verify_backup_manifest(self.backup)["schema_migration_attempted"],
            True,
        )
        with self.assertRaisesRegex(RuntimeError, "source-only rollback DENIED"):
            installer.restore(self.backup)
        for rel in self.relatives:
            self.assertEqual((self.live / rel).read_bytes(), b"CURRENT")
        self.restart_mock.assert_not_called()

    def test_legacy_backup_missing_schema_phase_fails_closed(self):
        del self.manifest["schema_migration_attempted"]
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, "source-only rollback DENIED"):
            installer.restore(self.backup)
        self.restart_mock.assert_not_called()

    def test_corrupt_second_backup_cannot_partially_restore_first(self):
        (self.backup / self.relatives[1]).write_bytes(b"TAMPERED")
        with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
            installer.restore(self.backup)
        for rel in self.relatives:
            self.assertEqual((self.live / rel).read_bytes(), b"CURRENT")
        self.restart_mock.assert_not_called()

    def test_missing_second_backup_cannot_partially_restore_first(self):
        (self.backup / self.relatives[1]).unlink()
        with self.assertRaises(RuntimeError):
            installer.restore(self.backup)
        self.assertEqual((self.live / self.relatives[0]).read_bytes(), b"CURRENT")

    def test_inventory_mismatch_rejected_before_restore(self):
        self.manifest["files"] = [str(self.relatives[0])]
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, "inventory"):
            installer.restore(self.backup)
        self.assertEqual((self.live / self.relatives[0]).read_bytes(), b"CURRENT")

    def test_run_id_mismatch_rejected_before_restore(self):
        self.manifest["run_id"] = "124"
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, "run_id mismatch"):
            installer.restore(self.backup)

    def test_malformed_mode_rejected(self):
        self.manifest[str(self.relatives[1])]["mode"] = 0o1000
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, "invalid mode"):
            installer.restore(self.backup)

    def test_dangling_live_symlink_is_not_recorded_absent(self):
        rel = Path("core/dangling.py")
        target = self.live / rel
        target.symlink_to(self.live / "nonexistent.py")
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            installer.backup_target(target, self.backup, {}, rel)

    def test_atomic_replace_refuses_live_symlink(self):
        rel = Path("core/redirect.py")
        target = self.live / rel
        target.symlink_to(self.live / "nonexistent.py")
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            installer.atomic_replace(self.backup / self.relatives[0], target, 0o640)

    def test_backup_digest_matches_original_bytes(self):
        rel = self.relatives[0]
        recorded = {}
        installer.backup_target(self.live / rel, self.backup, recorded, rel)
        self.assertEqual(recorded[str(rel)]["sha256"], hashlib.sha256(b"CURRENT").hexdigest())


if __name__ == "__main__":
    unittest.main()
