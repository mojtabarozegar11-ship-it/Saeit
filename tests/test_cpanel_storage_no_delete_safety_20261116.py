"""Protect cPanel storage and archives against obsolete auto-delete workflows.

Pure offline GitHub source inspections; no external tools or production access.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "zomorod-safe-backup-candidates-readonly-20261104.yml":
        "BACKUP_DEDUP_AND_QUARANTINE_DELETE=RETIRED",
    "zomorod-compact-two-legacy-saeit-backups.yml":
        "LEGACY_BACKUP_SOURCE_DELETION=RETIRED",
    "zomorod-safe-npm-cache-reclaim-20261104.yml":
        "AUTOMATIC_CPANEL_NPM_CACHE_DELETION=RETIRED",
}


class CpanelStorageNoDeleteContract(unittest.TestCase):
    def test_retired_workflows_keep_no_write_verifiable_status(self):
        for name, marker in WORKFLOWS.items():
            with self.subTest(name=name):
                body = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertIn(marker, body)
                for evidence in (
                    "CPANEL_SSH=NOT_REQUESTED",
                    "CPANEL_DELETE_ALLOWED=FALSE",
                    "BACKUPS_CHANGED=FALSE",
                    "PRODUCTION_FILES_CHANGED=FALSE",
                    "CRON_OR_SERVICE_CHANGED=FALSE",
                    "INDEPENDENT_RESTORE_VERIFICATION=REQUIRED",
                ):
                    self.assertIn(evidence, body)

    def test_no_secret_ssh_or_deletion_operation_reenabled(self):
        prohibited = (
            r"secrets\.",
            r"\bssh\s+-[A-Za-z]",
            r"\bscp\s+",
            r"\brsync\s+",
            r"\b(?:rmtree|unlink|rmdir)\s*\(",
            r"\brm\s+-[A-Za-z]*r",
            r"\bsystemctl\s+",
            r"\bcrontab\s+",
            r"\b(?:mysql|mariadb|mysqldump)\s+",
        )
        for name in WORKFLOWS:
            content = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            for pattern in prohibited:
                with self.subTest(name=name, pattern=pattern):
                    self.assertIsNone(re.search(pattern, content, flags=re.IGNORECASE))

    def test_no_unattended_schedule_or_manual_dispatch(self):
        for name in WORKFLOWS:
            content = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertNotRegex(content, r"(?m)^\s*(?:schedule|workflow_dispatch|pull_request):")
                self.assertRegex(content, r"(?m)^\s*permissions:\s*$")
                self.assertRegex(content, r"(?m)^\s*contents:\s*read\s*$")

    def test_workflow_changes_only_replay_inert_job(self):
        for name in WORKFLOWS:
            content = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("no-production-mutation:", content)
                self.assertIn("paths:", content)
                self.assertIn(name, content)
                self.assertNotIn("rm -rf", content)


if __name__ == "__main__":
    unittest.main()
