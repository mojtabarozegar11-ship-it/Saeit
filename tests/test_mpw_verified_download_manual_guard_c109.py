"""Source contract: old paid-download repair must never run from a main push.

No network, secrets, customer data, invoices, payments or host operations.
"""
import re
import unittest
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/mpw-buyer-verified-download-links-live-20261020.yml"
)


class VerifiedPaidDownloadOwnerReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.triggers, cls.jobs = cls.source.split("\njobs:\n", 1)
        cls.guard, cls.release = cls.jobs.split("\n  release:\n", 1)

    def test_01_no_automatic_publish_from_main_push(self):
        self.assertNotRegex(self.triggers, r"(?m)^  push:")
        self.assertNotRegex(self.triggers, r"(?m)^  schedule:")
        self.assertIn("  workflow_dispatch:", self.triggers)

    def test_02_pr_only_runs_pure_security_guard(self):
        self.assertIn("  pull_request:", self.triggers)
        self.assertIn("if: github.event_name == 'pull_request'", self.guard)
        self.assertIn("runs-on: ubuntu-latest", self.guard)
        self.assertNotIn("secrets.", self.guard)
        self.assertNotIn("ssh -", self.guard)
        self.assertNotIn("publish '$GITHUB_RUN_ID'", self.guard)

    def test_03_release_is_only_exact_main_owner_dispatch(self):
        for text in (
            "github.event_name == 'workflow_dispatch'",
            "github.actor == 'mojtabarozegar11-ship-it'",
            "github.ref == 'refs/heads/main'",
            "inputs.owner_approval == 'OWNER_APPROVED'",
        ):
            self.assertIn(text, self.release)
        self.assertIn("default: 'NO'", self.triggers)

    def test_04_release_requires_independent_restore_and_isolation(self):
        for name in (
            "MPW_BACKUP_RESTORE_VERIFIED",
            "MPW_ROLLBACK_VERIFIED",
            "MPW_TENANT_ISOLATION_VERIFIED",
            "MPW_DELIVERY_RIGHTS_RESTORE_VERIFIED",
        ):
            self.assertIn("vars." + name + " == 'true'", self.release)

    def test_05_release_commit_is_pinned_before_any_secrets(self):
        self.assertIn("vars.MPW_APPROVED_MAIN_SHA == github.sha", self.release)
        self.assertIn("REQUESTED_RELEASE_SHA: ${{ inputs.release_sha }}", self.release)
        check = self.release.index('[[ "$REQUESTED_RELEASE_SHA" == "$GITHUB_SHA" ]]')
        secret = self.release.index("secrets.")
        self.assertLess(check, secret)

    def test_06_no_automatic_success_claim_or_merchant_canary_bypass(self):
        self.assertNotIn("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=true", self.source)
        self.assertNotIn("MPW_COMMERCE_RELEASE_READY=true", self.source)
        self.assertNotIn("workflow_run:", self.triggers)

    def test_07_legacy_patch_is_scoped_and_rollback_kept(self):
        self.assertIn("scripts/mpw_live_checkout_status_download_contract_20261020.py", self.release)
        self.assertIn("Roll back only the checkout handler", self.release)
        self.assertIn("if: failure() && steps.publish.outcome == 'success'", self.release)


if __name__ == "__main__":
    unittest.main()
