"""Regression safety gates for VPS log deletion and protected recovery archives.

These tests inspect repository source only. They never access a host or data.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ROOT / ".github/workflows/vps-controlled-transient-cleanup-20261107.yml"
BACKUP = ROOT / ".github/workflows/vps-factory-safe-backup-retention-20261028.yml"
PAUSE = ROOT / ".github/workflows/vps-factory-low-disk-pause-20261029.yml"


class VpsCleanupSafetyTests(unittest.TestCase):
    def test_old_log_cleanup_is_inert_and_cannot_ssh(self):
        source = RETIRED.read_text(encoding="utf-8")
        self.assertIn("AGE_BASED_VPS_LOG_DELETION=RETIRED", source)
        self.assertIn("VPS_REMOTE_CONNECTION=NOT_REQUESTED", source)
        self.assertIn("BACKUPS_MODIFIED=FALSE", source)
        self.assertIn("PRODUCTION_FILES_MODIFIED=FALSE", source)
        # No runner secret, authenticated remote call, destructive operation,
        # scheduled repetition or manual dispatch should be added accidentally.
        forbidden = (
            r"secrets\.", r"ssh\s+-", r"scp\s+", r"rsync\s+",
            r"\brmtree\s*\(", r"\bunlink\s*\(",
            r"\brm\s+-[a-zA-Z]*r", r"\bshutil\.",
            r"\bcrontab\s+", r"\bsystemctl\s+",
            r"\bworkflow_dispatch\b", r"^\s*schedule\s*:",
        )
        for expression in forbidden:
            with self.subTest(forbidden=expression):
                self.assertIsNone(re.search(expression, source, flags=re.M | re.I))

    def test_vps_backup_deletion_hold_remains_active(self):
        source = BACKUP.read_text(encoding="utf-8")
        self.assertIn("HARD SAFETY HOLD", source)
        self.assertRegex(source, r"(?m)^\s*if:\s*\$\{\{\s*false\s*\}\}\s*$")
        self.assertIn("independent off-host recovery", source)

    def test_low_disk_pause_never_auto_resumes_factory(self):
        source = PAUSE.read_text(encoding="utf-8")
        self.assertIn("FACTORY_AUTO_RESUME=false", source)
        self.assertIn("FACTORY_LOW_DISK_PAUSE=production_schedulers_paused", source)
        self.assertIn("reserve_kib=524288", source)
        self.assertIn("FACTORY_LOW_DISK_PAUSE=not_required", source)


if __name__ == "__main__":
    unittest.main()
