"""Guard MojPlayWin store/main merge against legacy push-triggered host publishers.

No remote writes, SSH, payment, inbox reads, or external services. These checks
prevent a future edit from silently reactivating a retired publisher. They do
not replace an exhaustive workflow audit of all repository release paths.
"""
from pathlib import Path
import re
import unittest

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
RETIRED = {
    "mpw-main-book-payment-copy-fix-20261019.yml": ("exact_scope", "store.html"),
    "mpw-store-semantic-mainonly-20261027.yml": ("publish", "store.html"),
    "zomorod-office-login-route-release.yml": ("release", "config/urls.py"),
    "zomorod-office-root-fallback-release-20261031.yml": ("release", "config/urls.py"),
}


def split_workflow(filename):
    source = (WORKFLOWS / filename).read_text(encoding="utf-8")
    header, jobs = source.split("\njobs:\n", 1)
    return header, jobs


def job_header(jobs, job):
    match = re.search(
        r"(?ms)^  " + re.escape(job)
        + r":\s*\n(.*?)(?=^  [a-zA-Z][\w-]*:\s*\n|\Z)",
        jobs,
    )
    if match is None:
        raise AssertionError("Missing audited job: " + job)
    return match.group(1).split("\n    steps:", 1)[0]


class MojPlayWinSafeMainMerge(unittest.TestCase):
    def test_retired_publishers_are_unreachable_from_main_push(self):
        for filename, (job, impacted_path) in RETIRED.items():
            with self.subTest(workflow=filename):
                header, jobs = split_workflow(filename)
                self.assertIn("  push:", header)
                self.assertIn("branches: [main]", header)
                self.assertIn(impacted_path, header)
                # They have deliberately *not* been given workflow_dispatch.
                self.assertNotIn("workflow_dispatch:", header)
                jobtext = job_header(jobs, job)
                self.assertRegex(
                    jobtext,
                    r"(?m)^    if: github\.event_name == 'workflow_dispatch'\s*$",
                )
                self.assertNotRegex(jobtext, r"(?m)^    if:.*'push'")

    def test_obsolete_zomorod_validation_jobs_are_also_disabled(self):
        for filename in (
            "zomorod-office-login-route-release.yml",
            "zomorod-office-root-fallback-release-20261031.yml",
        ):
            with self.subTest(workflow=filename):
                _, jobs = split_workflow(filename)
                self.assertRegex(
                    job_header(jobs, "validate"),
                    r"(?m)^    if: github\.event_name == 'workflow_dispatch'\s*$",
                )

    def test_existing_store_publisher_requires_exact_legacy_commit_marker(self):
        header, jobs = split_workflow("mpw-store-sales-funnel-fix-20261024.yml")
        self.assertIn("core/templates/mojplaywin/store.html", header)
        jobtext = job_header(jobs, "publish-store-only")
        self.assertIn("contains(github.event.head_commit.message, '[MPW_STORE_SALES_FIX_20261024]')", jobtext)
        self.assertNotIn("github.event_name == 'workflow_dispatch' ||", jobtext)

    def test_current_site_and_company_release_jobs_are_dispatch_only(self):
        for filename, job in (
            ("mojplaywin-main-deploy.yml", "deploy-main"),
            ("zomorod-app-pages-deploy.yml", "publish"),
            ("mojplaywin-moj-prop-deploy.yml", "deploy"),
        ):
            with self.subTest(workflow=filename):
                header, jobs = split_workflow(filename)
                self.assertIn("workflow_dispatch:", header)
                self.assertIn(
                    "github.event_name == 'workflow_dispatch'",
                    job_header(jobs, job),
                )


if __name__ == "__main__":
    unittest.main()
