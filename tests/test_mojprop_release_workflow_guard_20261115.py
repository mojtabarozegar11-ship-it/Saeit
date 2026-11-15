"""No production interaction. Lock in the owner-approved deployment boundary."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml"


class MojPropSafeReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.validate, cls.deploy = cls.source.split("\n  deploy:\n", 1)
        cls.deploy = "\n  deploy:\n" + cls.deploy

    def test_pull_request_and_push_do_not_execute_production_deploy(self):
        self.assertIn("pull_request:", self.validate)
        self.assertIn("push:", self.validate)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.deploy)
        # The old rule used push as an alternate release trigger.
        self.assertNotIn("github.event_name == 'push' ||", self.deploy)
        self.assertNotIn("github.event_name == 'push' &&", self.deploy)

    def test_manual_release_requires_owner_approval_and_main_branch(self):
        self.assertIn("inputs.owner_approval == 'OWNER_APPROVED'", self.deploy)
        self.assertIn("github.ref == 'refs/heads/main'", self.deploy)
        self.assertIn("release_sha:", self.validate)
        self.assertIn("default: 'NO'", self.validate)

    def test_recovery_isolation_and_rollback_attestations_required(self):
        for field in (
            "vars.MOJPROP_BACKUP_RESTORE_VERIFIED == 'true'",
            "vars.MOJPROP_ROLLBACK_VERIFIED == 'true'",
            "vars.MOJPROP_TENANT_ISOLATION_VERIFIED == 'true'",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.deploy)

    def test_exact_commit_pin_is_checked_before_secret_setup(self):
        check = self.deploy.index("Fail closed unless this exact main commit is approved")
        secret = self.deploy.index("Configure pinned cPanel SSH from factory runner")
        self.assertLess(check, secret)
        self.assertIn('[[ "$REQUESTED_RELEASE_SHA" == "$GITHUB_SHA" ]]', self.deploy)

    def test_source_validation_runs_before_deploy_and_cannot_dispatch_it(self):
        self.assertIn("\n  validate:\n", self.validate)
        self.assertIn("needs: validate", self.deploy)


if __name__ == "__main__":
    unittest.main()
