"""Reject accidental/unauthorized backend releases without production access."""
from pathlib import Path
import unittest

WORKFLOW = (Path(__file__).resolve().parents[1] /
            ".github/workflows/mojprop-backend-controlled-release-20261115.yml")


class MojPropPinnedOwnerReleaseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.triggers, cls.jobs = cls.source.split("\njobs:\n", 1)
        cls.validate, cls.deploy = cls.jobs.split("\n  deploy:\n", 1)

    def test_01_no_push_or_pull_request_can_release(self):
        self.assertIn("  workflow_dispatch:", self.triggers)
        self.assertNotIn("  push:", self.triggers)
        self.assertNotIn("  pull_request:", self.triggers)
        self.assertNotIn("  schedule:", self.triggers)

    def test_02_only_exact_owner_can_invoke_backend_release(self):
        self.assertIn("github.actor == 'mojtabarozegar11-ship-it'", self.deploy)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.deploy)
        self.assertIn("github.ref == 'refs/heads/main'", self.deploy)
        self.assertIn("inputs.owner_approval == 'OWNER_APPROVED'", self.deploy)

    def test_03_sha_must_be_approved_outside_dispatch_input(self):
        self.assertIn("vars.MOJPROP_APPROVED_MAIN_SHA == github.sha", self.deploy)
        self.assertIn('[[ "$REQUESTED_RELEASE_SHA" == "$GITHUB_SHA" ]]', self.deploy)
        self.assertIn("default: 'NO'", self.triggers)
        self.assertIn("required: true", self.triggers)

    def test_04_real_restore_and_tenant_gate_stay_fail_closed(self):
        for name in ("MOJPROP_BACKUP_RESTORE_VERIFIED",
                     "MOJPROP_ROLLBACK_VERIFIED",
                     "MOJPROP_TENANT_ISOLATION_VERIFIED"):
            self.assertIn("vars." + name + " == 'true'", self.deploy)

    def test_05_release_ssh_secret_after_exact_SHA_check(self):
        self.assertLess(self.deploy.index('[[ "$REQUESTED_RELEASE_SHA" == "$GITHUB_SHA" ]]'),
                        self.deploy.index("secrets.SAEIT_HOST_SSH_PRIVATE_KEY"))

    def test_06_no_cost_or_chain_payment_approved_by_source(self):
        for unsafe in ("MOJPROP_BACKUP_RESTORE_VERIFIED: true",
                       "MOJPROP_ROLLBACK_VERIFIED: true",
                       "TRON_PAYMENT_ENABLED: true",
                       "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED: true"):
            self.assertNotIn(unsafe, self.source)


if __name__ == "__main__":
    unittest.main()
