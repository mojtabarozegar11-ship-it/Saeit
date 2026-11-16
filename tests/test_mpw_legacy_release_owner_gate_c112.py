"""C112: legacy TRON and buyer publishers must never deploy on a push.

This is a stdlib-only repository contract. It never accesses secrets,
customer data, cPanel, GitHub APIs, checkout or payment networks.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"
FILENAMES = (
    "mpw-tron-bounded-head-production-deploy-20261025.yml",
    "mpw-trongrid-indexer-production-deploy-20261025.yml",
    "mpw-legacy-checkout-fintech-v2-live-20261021.yml",
    "mpw-two-books-checkout-links-live-20261019.yml",
    "mpw-checkout-return-path-repair-20261024.yml",
)

class LegacyBuyerCheckoutManualOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = {name: (ROOT / name).read_text(encoding="utf-8") for name in FILENAMES}

    def test_01_all_five_original_legacy_workflows_are_covered(self):
        self.assertEqual(len(self.files), 5)
        self.assertEqual(len(set(FILENAMES)), 5)

    def test_02_no_push_pull_request_schedule_or_issue_comment_can_deploy(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                trigger = source.split("\njobs:\n", 1)[0]
                self.assertIn("  workflow_dispatch:", trigger)
                for forbidden in ("  push:", "  pull_request:", "  schedule:",
                                  "  issue_comment:", "  workflow_run:"):
                    self.assertNotIn(forbidden, trigger)

    def test_03_no_concurrent_actor_can_inherit_owner_authorization(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                self.assertIn("github.actor == 'mojtabarozegar11-ship-it'", source)
                self.assertIn("github.triggering_actor == 'mojtabarozegar11-ship-it'", source)
                self.assertIn("github.run_attempt == 1", source)

    def test_04_release_requires_exact_main_sha_from_separate_repo_approval(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                self.assertIn("github.ref == 'refs/heads/main'", source)
                self.assertIn("inputs.release_sha == github.sha", source)
                self.assertIn("vars.MPW_APPROVED_MAIN_SHA == github.sha", source)

    def test_05_explicit_case_sensitive_owner_choice_defaults_deny(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                self.assertIn("inputs.owner_approval == 'OWNER_APPROVED'", source)
                self.assertIn("options: ['NO', 'OWNER_APPROVED']", source)
                self.assertIn("default: 'NO'", source)

    def test_06_full_independent_restore_rollback_and_tenant_flags_all_required(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                for flag in ("MPW_BACKUP_RESTORE_VERIFIED",
                             "MPW_ROLLBACK_VERIFIED",
                             "MPW_TENANT_ISOLATION_VERIFIED"):
                    self.assertIn("vars." + flag + " == 'true'", source)
                self.assertIn("vars.MPW_LEGACY_RELEASE_ALLOWED == 'true'", source)

    def test_07_only_one_code_changing_release_job_and_it_is_fully_guarded(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                jobs = source.split("\njobs:\n", 1)[1]
                match = re.search(r"(?m)^  (deploy|release|publish):\n", jobs)
                self.assertIsNotNone(match)
                job = jobs[match.end():]
                self.assertIn("    if: >-", job[:850])
                self.assertIn("github.event_name == 'workflow_dispatch'", job[:850])
                self.assertIn("github.triggering_actor", job[:850])

    def test_08_cannot_publish_merchant_by_turning_on_canary_from_source(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                for unsafe in ("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=true",
                               "MPW_COMMERCE_RELEASE_READY=true",
                               "TRON_PAYMENT_ENABLED=true",
                               "MPW_BACKUP_RESTORE_VERIFIED: true"):
                    self.assertNotIn(unsafe, source)

    def test_09_preserve_original_source_scopes_and_rollback(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                self.assertIn("jobs:", source)
                self.assertIn("runs-on: ubuntu-latest", source)
                self.assertIn("steps:", source)

    def test_10_never_accept_branch_name_as_dispatch_release_sha(self):
        for name, source in self.files.items():
            with self.subTest(name=name):
                self.assertIn("release_sha:", source.split("\njobs:\n", 1)[0])
                self.assertNotIn("source_ref:", source.split("\njobs:\n", 1)[0])


if __name__ == "__main__":
    unittest.main()
