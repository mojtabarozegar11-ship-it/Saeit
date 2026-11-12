"""Regression contract for the two locked legacy MojPlayWin deployments and
the separately authorized, bounded main-site release workflow.

This is source-only verification. No test authorizes a release or weakens
the fail-closed host/backup/smoke/rollback requirements.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "mojplaywin-active-home-editorials.yml": "deploy-active-home",
    "mojplaywin-legacy-content-deploy.yml": "deploy-content",
}
MAIN = ROOT / ".github/workflows/mojplaywin-main-deploy.yml"


class ProtectedSubsiteDeployLockTests(unittest.TestCase):
    def test_legacy_shared_deploy_jobs_remain_hard_stopped(self):
        for filename, job_id in WORKFLOWS.items():
            with self.subTest(filename=filename):
                src = (ROOT / ".github" / "workflows" / filename).read_text(
                    encoding="utf-8"
                )
                self.assertIn("jobs:\n  " + job_id + ":\n", src)
                header = src.split("jobs:\n  " + job_id + ":\n", 1)[1]
                header = header.split("\n    steps:", 1)[0]
                self.assertRegex(header, r"(?m)^    if: \$\{\{ false \}\}$")
                self.assertNotRegex(
                    header, r"(?m)^    if: (?!\$\{\{ false \}\}).+$"
                )

    def test_main_release_requires_pinned_guarded_path(self):
        src = MAIN.read_text(encoding="utf-8")
        self.assertIn("jobs:\n  deploy-main:\n", src)
        header = src.split("jobs:\n  deploy-main:\n", 1)[1]
        header = header.split("\n    steps:", 1)[0]
        self.assertNotRegex(
            header, r"(?m)^    if: \$\{\{ false \}\}$"
        )
        for marker in (
            "branches: [main]",
            "permissions:\n  contents: read",
            "cancel-in-progress: false",
            "StrictHostKeyChecking yes",
            "PINNED_RELAY_READY",
            "source_ref=",
            "baseline_ref=",
            "MOJPLAYWIN_SAFE_MERGE_CHECK=passed",
            "Unsafe or incomplete MojPlayWin archive",
            "LIVE_ROUTE_OK",
            "INDEXNOW_KEY_LIVE=yes",
            "if: failure() && steps.deploy.outcome == 'success' && steps.smoke.outcome == 'failure'",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, src)
        self.assertLess(
            src.index("Validate source and pinned baseline"),
            src.index("Stage and install on the verified cPanel app"),
        )
        self.assertLess(
            src.index("Stage and install on the verified cPanel app"),
            src.index("Smoke-test MojPlayWin pages"),
        )
        self.assertLess(
            src.index("Smoke-test MojPlayWin pages"),
            src.index("Roll back if smoke checks fail"),
        )

    def test_only_two_legacy_workflows_are_locked(self):
        self.assertEqual(len(WORKFLOWS), 2)
        self.assertNotIn(MAIN.name, WORKFLOWS)
        for filename in WORKFLOWS:
            self.assertTrue(filename.startswith("mojplaywin-"))


if __name__ == "__main__":
    unittest.main()
