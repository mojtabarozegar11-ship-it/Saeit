"""Fail-closed gate for approved PR merge: never auto-write production host.

Covers both source-modifying workflows known to be triggered by Moj Prop,
its digital SKU PR, and the stacked educational signal PR. It does not
pretend to enumerate every workflow in the repository.
"""
from pathlib import Path
import unittest


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github/workflows"


class ManualOnlyHostReleaseTests(unittest.TestCase):
    def test_zomorod_publish_job_is_dispatch_only_with_full_attestation(self):
        source = (WORKFLOWS / "zomorod-app-pages-deploy.yml").read_text()
        self.assertIn("on:\n  push:", source)
        self.assertIn("jobs:\n  publish:\n    #", source)
        job = source.split("jobs:\n  publish:", 1)[1]
        required = (
            "if: github.event_name == 'workflow_dispatch'",
            '[[ "$GITHUB_REF" == "refs/heads/main" ]]',
            "OWNER_APPROVED: ${{ inputs.owner_approved_live_deploy }}",
            "BACKUP_RESTORE_VERIFIED: ${{ vars.ZOMOROD_BACKUP_RESTORE_VERIFIED }}",
            "ROLLBACK_VERIFIED: ${{ vars.ZOMOROD_ROLLBACK_VERIFIED }}",
            "TENANT_ISOLATION_VERIFIED: ${{ vars.ZOMOROD_TENANT_ISOLATION_VERIFIED }}",
            '[[ "$OWNER_APPROVED_SHA" == "$GITHUB_SHA" ]]',
            '[[ "$OWNER_APPROVED" == "true" ]]',
            '[[ "$BACKUP_RESTORE_VERIFIED" == "true" ]]',
            '[[ "$ROLLBACK_VERIFIED" == "true" ]]',
            '[[ "$TENANT_ISOLATION_VERIFIED" == "true" ]]',
        )
        for clause in required:
            with self.subTest(clause=clause):
                self.assertIn(clause, job)
        self.assertNotIn("github.event_name == 'push'", job)

    def test_mojprop_catalog_release_requires_manual_dispatch_and_owner_record(self):
        source = (WORKFLOWS / "mojplaywin-moj-prop-deploy.yml").read_text()
        self.assertIn("jobs:\n  deploy:", source)
        job = source.split("jobs:\n  deploy:", 1)[1]
        for clause in (
            "github.event_name == 'workflow_dispatch'",
            "github.ref == 'refs/heads/main'",
            "inputs.owner_approval == 'OWNER_APPROVED'",
            "vars.MOJPROP_BACKUP_RESTORE_VERIFIED == 'true'",
            "vars.MOJPROP_ROLLBACK_VERIFIED == 'true'",
            "vars.MOJPROP_TENANT_ISOLATION_VERIFIED == 'true'",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, job)
        self.assertNotIn("github.event_name == 'push'", job)


if __name__ == "__main__":
    unittest.main()
