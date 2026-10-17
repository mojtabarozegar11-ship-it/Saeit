"""Regression guard: no MojPlayWin shared Passenger publication from legacy workflows.

This checks job-level fail-closed locks. Source only; it does not authorize
merging a redesign, restarting Passenger, or making production changes.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "mojplaywin-main-deploy.yml": "deploy-main",
    "mojplaywin-active-home-editorials.yml": "deploy-active-home",
    "mojplaywin-legacy-content-deploy.yml": "deploy-content",
}


class ProtectedSubsiteDeployLockTests(unittest.TestCase):
    def test_all_three_shared_deploy_jobs_hard_stopped(self):
        for filename, job_id in WORKFLOWS.items():
            with self.subTest(filename=filename):
                file = ROOT / ".github" / "workflows" / filename
                src = file.read_text(encoding="utf-8")
                self.assertIn("jobs:\n  " + job_id + ":\n", src)
                job_header = src.split("jobs:\n  " + job_id + ":\n", 1)[1]
                job_header = job_header.split("\n    steps:", 1)[0]
                self.assertRegex(job_header, r"(?m)^    if: \$\{\{ false \}\}$")
                self.assertNotRegex(job_header, r"(?m)^    if: (?!\$\{\{ false \}\}).+$")

    def test_only_expected_legacy_workflows_locked(self):
        self.assertEqual(len(WORKFLOWS), 3)
        for filename in WORKFLOWS:
            self.assertTrue(filename.startswith("mojplaywin-"))

if __name__ == "__main__":
    unittest.main()
