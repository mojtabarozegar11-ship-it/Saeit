#!/usr/bin/env python3
"""Offline conflict tests for real read-only pre-switch PHP integrity verifier."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts/zomorod_business_pre_switch_drift_guard.py"
INSTALLER = ROOT / "scripts/zomorod_business_genetics_guarded_install.sh"
WORKFLOW = ROOT / ".github/workflows/zomorod-business-update.yml"
spec = importlib.util.spec_from_file_location("pre_switch_guard", GUARD)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PreSwitchDriftContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="zm-private-php-conflict-")
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.live_app = base / "app.php"
        self.live_dossier = base / "genetics-center.php"
        self.backup_app = base / "backups" / "app.php"
        self.backup_dossier = base / "backups" / "genetics-center.php"
        self.candidate_app = base / "new-app.php"
        self.candidate_dossier = base / "new-dossier.php"
        self.backup_app.parent.mkdir()
        self.live_app.write_bytes(b"<?php echo 'LIVE 01';")
        self.backup_app.write_bytes(self.live_app.read_bytes())
        self.candidate_app.write_bytes(b"<?php echo 'CANDIDATE';")
        self.candidate_dossier.write_bytes(b"<?php echo 'DOSSIER';")
        self.app_sha = digest(self.live_app)
        self.candidate_app_sha = digest(self.candidate_app)
        self.candidate_dossier_sha = digest(self.candidate_dossier)

    def args(self):
        return (
            self.live_app, self.live_dossier,
            self.backup_app, self.backup_dossier,
            self.candidate_app, self.candidate_dossier,
            self.app_sha, "ABSENT",
            self.candidate_app_sha, self.candidate_dossier_sha,
        )

    def test_exact_source_backup_and_candidate_verified_without_writes(self):
        before = [p.read_bytes() for p in (self.live_app, self.backup_app, self.candidate_app)]
        guard.check(*self.args())
        self.assertEqual(
            [p.read_bytes() for p in (self.live_app, self.backup_app, self.candidate_app)],
            before,
        )
        command = [sys.executable, str(GUARD), *map(str, self.args())]
        result = subprocess.run(command, capture_output=True, text=True, timeout=6)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PRE_SWITCH_GUARD=SOURCE_BACKUP_AND_CANDIDATES_MATCH", result.stdout)

    def test_concurrent_live_app_edit_blocks_without_touching_backup(self):
        before = self.backup_app.read_bytes()
        self.live_app.write_bytes(b"<?php echo 'LIVE 02';")
        self.assertEqual(len(self.live_app.read_bytes()), len(before))
        with self.assertRaisesRegex(guard.GuardViolation, "LIVE_APP_CHANGED"):
            guard.check(*self.args())
        self.assertEqual(self.backup_app.read_bytes(), before)

    def test_modified_backup_blocks_release(self):
        self.backup_app.write_bytes(b"<?php echo 'LIVE 03';")
        with self.assertRaisesRegex(guard.GuardViolation, "BACKUP_APP_NOT_EXACT"):
            guard.check(*self.args())

    def test_dossier_appearing_after_absent_baseline_blocks(self):
        self.live_dossier.write_bytes(b"<?php echo 'CONCURRENT FILE';")
        with self.assertRaisesRegex(guard.GuardViolation, "UNEXPECTED_DOSSIER_APPEARED"):
            guard.check(*self.args())

    def test_candidate_changed_after_stage_blocks(self):
        self.candidate_app.write_bytes(b"<?php echo 'OTHER APP';")
        with self.assertRaisesRegex(guard.GuardViolation, "CANDIDATE_APP_CHANGED"):
            guard.check(*self.args())

    def test_dangling_symlink_as_backup_dossier_blocks(self):
        self.backup_dossier.symlink_to(self.backup_app.parent / "missing.php")
        with self.assertRaisesRegex(guard.GuardViolation, "UNEXPECTED_DOSSIER_APPEARED"):
            guard.check(*self.args())

    def test_existing_dossier_requires_exact_live_and_backup(self):
        self.live_dossier.write_bytes(b"<?php echo 'OLD DOSSIER';")
        self.backup_dossier.write_bytes(self.live_dossier.read_bytes())
        args = list(self.args())
        args[7] = digest(self.live_dossier)
        guard.check(*args)
        self.backup_dossier.write_bytes(b"<?php echo 'OLD CHANGED';")
        with self.assertRaisesRegex(guard.GuardViolation, "BACKUP_DOSSIER_NOT_EXACT"):
            guard.check(*args)

    def test_pre_switch_runs_before_first_live_rename(self):
        installer = INSTALLER.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        pre_check = installer.index('python3 -B "$stage/pre-switch.py"')
        live_move = installer.index('mv -f "$private/.genetics-center.new-$release_sha" "$live_dossier"')
        self.assertLess(pre_check, live_move)
        self.assertIn("cat > '$stage/pre-switch.py'", workflow)
        self.assertNotIn("  push:\n", workflow)


if __name__ == "__main__":
    unittest.main()
