"""A source merge of the 17 financial brands cannot restart production.

Review-only tests: no SSH, hosting, GitHub dispatch, real wallet or spend.
"""
import unittest
import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class ManualSignalDeploymentTests(unittest.TestCase):
    def test_saman_main_push_cannot_execute_release_job(self):
        source = (WORKFLOWS / "mojplaywin-saman-deploy.yml").read_text()
        self.assertIn("on:\n  push:\n    branches: [main]", source)
        self.assertIn("workflow_dispatch:\n    inputs:", source)
        self.assertIn("jobs:\n  deploy-saman:\n", source)
        job = source.split("jobs:\n  deploy-saman:", 1)[1]
        self.assertIn("if: github.event_name == 'workflow_dispatch'", job)
        self.assertNotIn("if: github.event_name == 'push'", job)

    def test_dispatch_cannot_touch_host_without_owner_rollback_and_sha(self):
        source = (WORKFLOWS / "mojplaywin-saman-deploy.yml").read_text()
        checks = (
            "owner_approved_live_release:",
            "approved_release_sha:",
            "required: true",
            "default: false",
            "OWNER_APPROVED: ${{ inputs.owner_approved_live_release }}",
            "REVIEWED_SHA: ${{ inputs.approved_release_sha }}",
            "RESTORE_PROVEN: ${{ vars.MPW_SAMAN_BACKUP_RESTORE_VERIFIED }}",
            "ROLLBACK_PROVEN: ${{ vars.MPW_SAMAN_ROLLBACK_VERIFIED }}",
            "TENANTS_ISOLATED: ${{ vars.MPW_SAMAN_TENANT_ISOLATION_VERIFIED }}",
            '[[ "$OWNER_APPROVED" == "true" ]]',
            '[[ "$REVIEWED_SHA" == "$GITHUB_SHA" ]]',
            '[[ "$RESTORE_PROVEN" == "true" ]]',
            '[[ "$ROLLBACK_PROVEN" == "true" ]]',
            '[[ "$TENANTS_ISOLATED" == "true" ]]',
        )
        for check in checks:
            with self.subTest(check=check):
                self.assertIn(check, source)
        first_check = source.index("- name: Require pinned owner-approved SAMAN release")
        last_assertion = source.index('[[ "$TENANTS_ISOLATED" == "true" ]]')
        ssh = source.index("- name: Configure pinned SSH relay")
        self.assertLess(first_check, last_assertion)
        self.assertLess(last_assertion, ssh)

    def test_zomorod_and_mojprop_host_write_jobs_still_manual(self):
        expected = (
            ("zomorod-app-pages-deploy.yml", "publish"),
            ("mojplaywin-moj-prop-deploy.yml", "deploy"),
        )
        for filename, jobname in expected:
            with self.subTest(filename=filename):
                source = (WORKFLOWS / filename).read_text()
                # YAML may put a validate job before deploy. Locate the
                # precise top-level job, not a brittle jobs:<newline>deploy pair.
                match = re.search(
                    r"(?m)^  " + re.escape(jobname) + r":\\s*$", source
                )
                self.assertIsNotNone(match, "Missing release job " + jobname)
                rest = source[match.end():]
                next_job = re.search(r"(?m)^  [a-zA-Z][a-zA-Z0-9_-]*:\\s*$", rest)
                job = rest[:next_job.start()] if next_job else rest
                self.assertIn("github.event_name == 'workflow_dispatch'", job)
                self.assertNotIn("github.event_name == 'push'", job)


if __name__ == "__main__":
    unittest.main()
