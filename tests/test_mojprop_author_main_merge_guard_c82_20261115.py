"""Fail-closed release regression for Moj Prop migrations changing config/urls.py.

These tests inspect repository workflow source only; no host action happens.
"""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/zomorod-persian-author-static-safe-20261021.yml"


class AuthorSiteManualReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.header, cls.job_source = cls.source.split("\njobs:\n", 1)
        cls.deploy = "\n  deploy:\n" + cls.job_source.split("\n  deploy:\n", 1)[1]

    def test_source_changes_on_main_may_validate_but_not_ssh(self):
        self.assertIn("  push:\n    branches: [main]", self.header)
        self.assertIn("  pull_request:\n    branches: [main]", self.header)
        self.assertIn("  workflow_dispatch:\n    inputs:", self.header)
        self.assertIn("config/urls.py", self.header)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.deploy)
        self.assertNotIn("github.event_name != 'pull_request'", self.deploy)

    def test_manual_approval_and_pinned_commit_checked_before_ssh(self):
        markers = (
            "owner_approved_author_release:", "reviewed_release_sha:",
            "default: false", "required: true",
            "OWNER_APPROVED: ${{ inputs.owner_approved_author_release }}",
            "RELEASE_SHA: ${{ inputs.reviewed_release_sha }}",
            '[[ "$OWNER_APPROVED" == "true" ]]',
            '[[ "$RELEASE_SHA" == "$GITHUB_SHA" ]]',
            '[[ "$GITHUB_REF" == "refs/heads/main" ]]',
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        self.assertLess(
            self.deploy.index("- name: Refuse unreviewed author publication"),
            self.deploy.index("- name: Establish pinned SSH relay"),
        )

    def test_real_restore_rollback_and_tenant_evidence_required(self):
        for key in (
            "ZM_AUTHOR_BACKUP_RESTORE_VERIFIED",
            "ZM_AUTHOR_ROLLBACK_VERIFIED",
            "ZM_AUTHOR_TENANT_ISOLATION_VERIFIED",
        ):
            with self.subTest(key=key):
                self.assertIn("vars." + key, self.deploy)
        for key in (
            "RESTORE_VERIFIED", "ROLLBACK_VERIFIED", "TENANT_ISOLATION_VERIFIED"
        ):
            with self.subTest(key=key):
                self.assertIn('[[ "
        self.assertLess(
            self.deploy.index('[[ "$TENANT_ISOLATION_VERIFIED" == "true" ]]'),
            self.deploy.index("- name: Establish pinned SSH relay"),
        )


if __name__ == "__main__":
    unittest.main()
 + key + '" == "true" ]]', self.deploy)
        self.assertLess(
            self.deploy.index('[[ "$TENANT_ISOLATION_VERIFIED" == "true" ]]'),
            self.deploy.index("- name: Establish pinned SSH relay"),
        )


if __name__ == "__main__":
    unittest.main()
