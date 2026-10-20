"""Static fail-closed contract for the privileged, explicitly manual backup job.

No SSH, no GitHub credentials, no production data or workflow dispatches.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mojplaywin-v3-owner-manual-backup.yml"


class OwnerOnlyManualBackupPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf8")

    def test_manual_only_never_automatic_push_or_pr(self):
        head = self.text.split("\npermissions:", 1)[0]
        self.assertIn("on:\n  workflow_dispatch:", head)
        for forbidden in ("\n  push:", "\n  pull_request:", "\n  schedule:",
                          "repository_dispatch:", "workflow_run:"):
            self.assertNotIn(forbidden, head)

    def test_owner_and_production_branch_are_required(self):
        self.assertIn("github.repository == 'mojtabarozegar11-ship-it/Saeit'", self.text)
        self.assertIn("github.ref == 'refs/heads/main'", self.text)
        self.assertIn("github.actor == 'mojtabarozegar11-ship-it'", self.text)
        self.assertIn("inputs.approval == 'APPROVE-PRIVATE-BACKUP-NO-PUBLISH'", self.text)
        self.assertIn("inputs.data_transit_acknowledged == true", self.text)
        self.assertIn("data_transit_acknowledged:", self.text)
        self.assertIn("default: false", self.text)
        self.assertIn("required: true", self.text)

    def test_scoped_script_and_non_release_evidence(self):
        self.assertIn("scripts/mojplaywin_backup_gzip_runner_v3.py", self.text)
        self.assertIn("--owner-approved", self.text)
        self.assertIn("V3_REAL_ISOLATED_RESTORE_COMPLETED=false", self.text)
        self.assertIn("V3_PUBLIC_RELEASE_AUTHORIZED=false", self.text)
        self.assertNotIn("secrets.GITHUB_TOKEN", self.text)
        self.assertNotIn("persist-credentials: true", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn("if: always()", self.text)
        self.assertIn('rm -rf -- "$RUNNER_TEMP/mojplaywin-inventory-ssh"', self.text)


if __name__ == "__main__":
    unittest.main()
