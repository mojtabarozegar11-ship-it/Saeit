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
    "mojplaywin-saman-deploy.yml": "deploy-saman",
    "zomorod-app-pages-deploy.yml": "publish",
}


class ManualDeployGuardTests(unittest.TestCase):
    @staticmethod
    def _condition(job_source):
        match = re.search(
            r"(?ms)^    if:\s*(.*?)(?=\n    (?:runs-on|timeout-minutes|needs|strategy|environment):|\Z)",
            job_source.split("\n    steps:", 1)[0],
        )
        if match is None:
            return None
        condition = " ".join(line.strip() for line in match.group(1).splitlines())
        condition = condition.replace(">-", " ").replace(">", " ").strip()
        return " ".join(condition.split())

    def test_all_sensitive_jobs_are_dispatch_only(self):
        for filename, job in WORKFLOWS.items():
            with self.subTest(workflow=filename):
                source = (ROOT / ".github" / "workflows" / filename).read_text("utf-8")
                self.assertIn("workflow_dispatch:", source.split("\njobs:", 1)[0])
                job_source = source.split("\n  " + job + ":", 1)[1]
                condition = self._condition(job_source)
                self.assertIsNotNone(condition)
                expected = "github.event_name == 'workflow_dispatch'"
                if filename == "mojplaywin-moj-prop-deploy.yml":
                    self.assertIn("owner_approved_static_release:", source)
                    expected += " && inputs.owner_approved_static_release == true"
                self.assertTrue(condition == expected or condition.startswith(expected + " && "))
                self.assertNotIn("github.event_name == 'push'", condition)

    def test_main_push_does_not_retain_unconditional_production_job(self):
        for filename, job in WORKFLOWS.items():
            with self.subTest(workflow=filename):
                source = (ROOT / ".github" / "workflows" / filename).read_text("utf-8")
                header = source.split("\njobs:", 1)[0]
                self.assertIn("branches: [main]", header)
                job_source = source.split("\n  " + job + ":", 1)[1]
                condition = self._condition(job_source)
                self.assertIsNotNone(condition)
                self.assertTrue(condition.startswith("github.event_name == 'workflow_dispatch'"))
                self.assertNotIn("github.event_name == 'push'", condition)


if __name__ == "__main__":
    unittest.main()
