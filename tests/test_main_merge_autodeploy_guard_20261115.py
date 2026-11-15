"""Regression: merging to main must never trigger a write-capable host deploy.

This covers the two workflows directly affected by the Moj Prop/signal PRs.
A green test is not proof of a restored database or readiness for manual deploy.
"""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class MainMergeCannotPublishTests(unittest.TestCase):
    def test_zomorod_host_job_is_dispatch_only_and_owner_attested(self):
        text = (ROOT / "zomorod-app-pages-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("on:\n  push:", text)  # CI may still validate pushes
        self.assertIn("jobs:\n  publish:\n    #", text)
        publish = text.split("jobs:\n  publish:", 1)[1]
        for clause in (
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
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, publish)
        self.assertNotIn("github.event_name == 'push'", publish)

    def test_mojprop_catalog_job_remains_manual_only(self):
        text = (ROOT / "mojplaywin-moj-prop-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("\n  deploy:\n", text)
        deploy = text.split("\n  deploy:", 1)[1]
        self.assertIn("github.event_name == 'workflow_dispatch'", deploy)
        self.assertNotIn("github.event_name == 'push'", deploy)
        self.assertTrue(
            "inputs.owner_approved_static_release == true" in deploy
            or "inputs.owner_approval == 'OWNER_APPROVED'" in deploy
        )


if __name__ == "__main__":
    unittest.main()
