"""Owner-approved merge must not automatically SSH/deploy unrelated sites.

This test protects four identified production workflows. It is NOT an
exhaustive repository-wide trigger audit or backup/rollback verification.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "mojplaywin-moj-prop-deploy.yml": "deploy",
    "mojplaywin-main-deploy.yml": "deploy-main",
    "mojplaywin-farnaz-deploy.yml": "deploy",
    "zomorod-app-pages-deploy.yml": "publish",
}


class ManualDeployGuardTests(unittest.TestCase):
    def test_all_sensitive_jobs_are_dispatch_only(self):
        for filename, job in WORKFLOWS.items():
            with self.subTest(workflow=filename):
                source = (ROOT / ".github" / "workflows" / filename).read_text("utf-8")
                self.assertIn("workflow_dispatch:", source.split("\njobs:", 1)[0])
                condition = "github.event_name == 'workflow_dispatch'"
                if filename == "mojplaywin-moj-prop-deploy.yml":
                    self.assertIn("owner_approved_static_release:", source)
                    condition += " && inputs.owner_approved_static_release == true"
                pattern = (r"(?m)^  " + re.escape(job) + r":\n"
                           r"(?:    \#.*\n)*"
                           r"    if: " + re.escape(condition) + r"$")
                self.assertRegex(source, pattern)

    def test_main_push_does_not_retain_unconditional_production_job(self):
        for filename, job in WORKFLOWS.items():
            with self.subTest(workflow=filename):
                source = (ROOT / ".github" / "workflows" / filename).read_text("utf-8")
                header = source.split("\njobs:", 1)[0]
                self.assertIn("branches: [main]", header)
                job_source = source.split("\n  " + job + ":", 1)[1]
                self.assertRegex(
                    job_source[:400],
                    r"(?m)^    if: github\.event_name == 'workflow_dispatch'",
                )
                self.assertNotIn(
                    "if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'",
                    job_source[:300],
                )


if __name__ == "__main__":
    unittest.main()
