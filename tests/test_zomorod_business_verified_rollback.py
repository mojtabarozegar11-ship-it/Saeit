#!/usr/bin/env python3
"""Synthetic private PHP rollback tests. Never reads or modifies cPanel."""
import hashlib
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/zomorod_business_verified_rollback.py"
INSTALLER = ROOT / "scripts/zomorod_business_genetics_guarded_install.sh"
WORKFLOW = ROOT / ".github/workflows/zomorod-business-update.yml"
spec = importlib.util.spec_from_file_location("verified_rollback", SCRIPT)
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VerifiedRollbackContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="zm-verified-rollback-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.private = root / "private"
        self.backup = root / "backup"
        self.private.mkdir(mode=0o700)
        self.backup.mkdir(mode=0o700)
        self.release = "a" * 40
        self.old = b"<?php echo 'ORIGINAL';"
        self.new = b"<?php echo 'NEW-APP';"
        self.dossier_new = b"<?php echo 'NEW-DOSSIER';"
        (self.backup / "app.php").write_bytes(self.old)
        (self.private / "app.php").write_bytes(self.new)
        (self.private / "genetics-center.php").write_bytes(self.dossier_new)
        self.old_digest = digest(self.old)
        self.new_digest = digest(self.new)
        self.dossier_digest = digest(self.dossier_new)

    def run_restore(self, expected_dossier="ABSENT"):
        return helper.restore(
            self.private, self.backup, self.release,
            self.old_digest, expected_dossier, self.new_digest, self.dossier_digest,
        )

    def test_restores_original_app_and_absent_dossier(self):
        result = self.run_restore()
        self.assertEqual(result["result"], "VERIFIED")
        self.assertEqual(result["conflicts_preserved"], "0")
        self.assertEqual((self.private / "app.php").read_bytes(), self.old)
        self.assertFalse((self.private / "genetics-center.php").exists())
        self.assertEqual((self.backup / "app.php").read_bytes(), self.old)

    def test_restores_original_existing_dossier(self):
        original_dossier = b"<?php echo 'OLD-DOSSIER';"
        (self.backup / "genetics-center.php").write_bytes(original_dossier)
        result = self.run_restore(digest(original_dossier))
        self.assertEqual(result["result"], "VERIFIED")
        self.assertEqual((self.private / "genetics-center.php").read_bytes(), original_dossier)

    def test_preserves_concurrent_app_edit_before_restoring(self):
        concurrent = b"<?php echo 'OTHER WRITER';"
        (self.private / "app.php").write_bytes(concurrent)
        result = self.run_restore()
        self.assertEqual(result["conflicts_preserved"], "1")
        archived = self.backup / ("concurrent-app-" + self.release + ".php")
        self.assertEqual(archived.read_bytes(), concurrent)
        self.assertEqual((self.private / "app.php").read_bytes(), self.old)

    def test_preserves_unexpected_new_dossier(self):
        concurrent = b"<?php echo 'CONCURRENT DOSSIER';"
        (self.private / "genetics-center.php").write_bytes(concurrent)
        result = self.run_restore()
        self.assertEqual(result["conflicts_preserved"], "1")
        archived = self.backup / ("concurrent-dossier-" + self.release + ".php")
        self.assertEqual(archived.read_bytes(), concurrent)
        self.assertFalse((self.private / "genetics-center.php").exists())

    def test_bad_backup_aborts_before_changing_live(self):
        before = (self.private / "app.php").read_bytes()
        (self.backup / "app.php").write_bytes(b"<?php echo 'TAMPERED';")
        with self.assertRaisesRegex(helper.RestoreError, "BACKUP_APP_INVALID"):
            self.run_restore()
        self.assertEqual((self.private / "app.php").read_bytes(), before)

    def test_dangling_symlink_backup_dossier_rejected(self):
        (self.backup / "genetics-center.php").symlink_to(self.backup / "missing.php")
        with self.assertRaisesRegex(helper.RestoreError, "UNEXPECTED_BACKUP_DOSSIER"):
            self.run_restore()
        self.assertEqual((self.private / "app.php").read_bytes(), self.new)

    def test_dangling_conflict_archive_prevents_partial_quarantine(self):
        (self.private / "app.php").write_bytes(b"<?php echo 'OTHER WRITER';")
        archive = self.backup / ("concurrent-dossier-" + self.release + ".php")
        archive.symlink_to(self.backup / "missing")
        with self.assertRaisesRegex(helper.RestoreError, "CONFLICT_ARCHIVE_ALREADY_EXISTS"):
            self.run_restore()
        self.assertEqual((self.private / "app.php").read_bytes(), b"<?php echo 'OTHER WRITER';")
        self.assertFalse((self.backup / ("concurrent-app-" + self.release + ".php")).exists())
        self.assertFalse((self.private / (".rollback-app-ready-" + self.release)).exists())
        self.assertFalse((self.private / (".rollback-dossier-ready-" + self.release)).exists())

    def test_invalid_dossier_symlink_refuses_before_touching_concurrent_app(self):
        concurrent = b"<?php echo 'CONCURRENT-APP-KEEP';"
        (self.private / "app.php").write_bytes(concurrent)
        dossier = self.private / "genetics-center.php"
        dossier.unlink()
        dossier.symlink_to(self.private / "missing-dossier.php")
        with self.assertRaisesRegex(helper.RestoreError, "UNSAFE_FILE"):
            self.run_restore()
        self.assertEqual((self.private / "app.php").read_bytes(), concurrent)
        self.assertTrue(dossier.is_symlink())
        self.assertFalse((self.backup / ("concurrent-app-" + self.release + ".php")).exists())
        self.assertFalse((self.private / (".rollback-app-ready-" + self.release)).exists())

    def test_invalid_live_app_symlink_refuses_without_staging(self):
        app = self.private / "app.php"
        app.unlink()
        app.symlink_to(self.backup / "app.php")
        with self.assertRaisesRegex(helper.RestoreError, "UNSAFE_FILE"):
            self.run_restore()
        self.assertTrue(app.is_symlink())
        self.assertFalse((self.private / (".rollback-app-ready-" + self.release)).exists())

    def test_concurrent_file_archive_is_copy_not_move(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("backup_copy(live, target, actual)", source)
        self.assertNotIn("os.replace(live, target)", source)
        self.assertIn("LIVE_CHANGED_DURING_RECOVERY_PREP", source)

    def test_existing_recovery_stage_refuses_reuse(self):
        (self.private / (".rollback-app-ready-" + self.release)).write_bytes(b"DO_NOT_REPLACE")
        with self.assertRaisesRegex(helper.RestoreError, "RECOVERY_STAGE_ALREADY_EXISTS"):
            self.run_restore()
        self.assertEqual((self.private / "app.php").read_bytes(), self.new)

    def test_insecure_backup_directory_rejected(self):
        self.backup.chmod(0o755)
        with self.assertRaisesRegex(helper.RestoreError, "INSECURE_BACKUP_DIRECTORY"):
            self.run_restore()

    def test_integrated_installer_and_workflow_contract(self):
        installer = INSTALLER.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('python3 -B "$stage/rollback.py"', installer)
        self.assertIn("BUSINESS_GENETICS_ROLLBACK=verified", installer)
        self.assertIn("BUSINESS_GENETICS_ROLLBACK=FAILED_MANUAL_RECOVERY_REQUIRED", installer)
        self.assertNotIn("BUSINESS_GENETICS_ROLLBACK=restored", installer)
        self.assertIn("cat > '$stage/rollback.py'", workflow)
        self.assertNotIn("  push:\n", workflow)
        self.assertNotIn('rm -f "$live_dossier"', installer)


if __name__ == "__main__":
    unittest.main()
