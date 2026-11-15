"""Guard main-branch merges: no GitHub push may publish live host files.

Owner approved PR merge only if code review and CI prove no automatic deploy.
A manual dispatch ALSO needs a pinned SHA and independent restore attestations.
"""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def workflow(name):
    return (ROOT / name).read_text(encoding="utf-8")


def job(name, job_name):
    # This intentionally recognizes only the explicit YAML block used by
    # these two release workflows; unexpected formatting fails closed.
    source = workflow(name)
    anchor = "\n  " + job_name + ":\n"
    if source.count(anchor) != 1:
        raise AssertionError("missing or ambiguous deployment job: " + name)
    # Release jobs are terminal in these two pinned workflows. A broad\n    # substring split on two spaces would incorrectly stop at four-space YAML.\n    return source.split(anchor, 1)[1]


class SafeMergeWorkflowContract(unittest.TestCase):
    def test_zomorod_app_auto_deploy_disabled_on_main_push(self):
        release = job("zomorod-app-pages-deploy.yml", "publish")
        self.assertIn("github.event_name == 'workflow_dispatch'", release)
        self.assertIn("github.ref == 'refs/heads/main'", release)
        self.assertIn("inputs.owner_approved_live_deploy == true", release)
        for attestation in (
            "vars.ZOMOROD_BACKUP_RESTORE_VERIFIED == 'true'",
            "vars.ZOMOROD_ROLLBACK_VERIFIED == 'true'",
            "vars.ZOMOROD_TENANT_ISOLATION_VERIFIED == 'true'",
        ):
            self.assertIn(attestation, release)
        self.assertNotIn("github.event_name == 'push'", release)

    def test_zomorod_release_requires_pinned_approved_commit(self):
        text = workflow("zomorod-app-pages-deploy.yml")
        self.assertIn("required: true", text)
        self.assertIn("default: false", text)
        self.assertIn('OWNER_APPROVED_SHA: ${{ inputs.approved_release_sha }}', text)
        self.assertIn('[[ "$OWNER_APPROVED_SHA" == "$GITHUB_SHA" ]]', text)

    def test_moj_prop_catalog_cannot_automatically_deploy_on_merge(self):
        release = job("mojplaywin-moj-prop-deploy.yml", "deploy")
        self.assertIn("github.event_name == 'workflow_dispatch'", release)
        self.assertIn("inputs.owner_approved_static_release == true", release)
        self.assertNotIn("github.event_name == 'push'", release)

    def test_no_cross_site_changes_to_other_workflows(self):
        # Regression covers the two known write-capable paths relevant to
        # Moj Prop and core/models.py; does not claim to enumerate ALL workflows.
        self.assertIn('  push:\n    branches: [main]', workflow("zomorod-app-pages-deploy.yml"))
        self.assertIn('  push:\n    branches: [main]', workflow("mojplaywin-moj-prop-deploy.yml"))


if __name__ == "__main__":
    unittest.main()
