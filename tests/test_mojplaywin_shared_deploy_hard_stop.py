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

    def test_main_push_is_never_equivalent_to_explicit_manual_release(self):
        from scripts.mojplaywin_detect_deploy_triggers import (
            manual_main_deployment_guarded,
        )
        source = MAIN.read_text(encoding="utf-8")
        header = source.split("\njobs:", 1)[0]
        self.assertTrue(manual_main_deployment_guarded(source, header))
        pushed = source.replace(
            "if: github.event_name == 'workflow_dispatch'",
            "if: github.event_name == 'push'",
            1,
        )
        self.assertFalse(manual_main_deployment_guarded(pushed, header))
        no_dispatch = header.replace("  workflow_dispatch:", "")
        self.assertFalse(manual_main_deployment_guarded(source, no_dispatch))

    def test_all_release_jobs_are_manual_without_unreviewed_push(self):
        from scripts.mojplaywin_detect_deploy_triggers import (
            MANUAL_RELEASE_JOBS, manual_release_job_guarded,
        )
        self.assertEqual(len(MANUAL_RELEASE_JOBS), 4)
        for filename, job in MANUAL_RELEASE_JOBS.items():
            with self.subTest(filename=filename, job=job):
                source = (ROOT / ".github/workflows" / filename).read_text("utf-8")
                header = source.split("\njobs:", 1)[0]
                self.assertTrue(manual_release_job_guarded(
                    source, header, job,
                    require_static_owner_approval=(
                        filename == "mojplaywin-moj-prop-deploy.yml"
                    ),
                ))
                unsafe = source.replace(
                    "if: github.event_name == 'workflow_dispatch'",
                    "if: github.event_name == 'push'",
                    1,
                )
                self.assertFalse(manual_release_job_guarded(
                    unsafe, header, job,
                    require_static_owner_approval=(
                        filename == "mojplaywin-moj-prop-deploy.yml"
                    ),
                ))

    def test_mojprop_cannot_publish_without_owner_release_input(self):
        from scripts.mojplaywin_detect_deploy_triggers import manual_release_job_guarded
        source = (ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text("utf-8")
        header = source.split("\njobs:", 1)[0]
        self.assertTrue(manual_release_job_guarded(
            source, header, "deploy", require_static_owner_approval=True,
        ))
        downgraded = source.replace(
            " && inputs.owner_approved_static_release == true", ""
        )
        self.assertFalse(manual_release_job_guarded(
            downgraded, header, "deploy", require_static_owner_approval=True,
        ))

    def test_only_two_legacy_workflows_are_locked(self):
        self.assertEqual(len(WORKFLOWS), 2)
        self.assertNotIn(MAIN.name, WORKFLOWS)
        for filename in WORKFLOWS:
            self.assertTrue(filename.startswith("mojplaywin-"))


if __name__ == "__main__":
    unittest.main()
