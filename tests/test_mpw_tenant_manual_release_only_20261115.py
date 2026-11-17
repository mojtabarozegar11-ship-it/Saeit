"""Static safety contract: MojPlayWin subsite merges cannot deploy to cPanel."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SAFE_SUBSITES = (
    ".github/workflows/mojplaywin-zahra-deploy.yml",
    ".github/workflows/mojplaywin-studio-raha-deploy.yml",
)


class TenantManualReleaseSafetyTests(unittest.TestCase):
    def test_no_push_merge_can_enter_subsite_deployment(self):
        for name in SAFE_SUBSITES:
            with self.subTest(file=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn("\n  deploy:\n", source)
                deploy = source.split("\n  deploy:\n", 1)[1]
                self.assertIn("github.event_name == 'workflow_dispatch'", deploy)
                self.assertNotIn("github.event_name == 'push' ||", deploy)
                self.assertIn("github.ref == 'refs/heads/main'", deploy)

    def test_each_release_needs_independent_restore_rollback_isolation_proof(self):
        for name in SAFE_SUBSITES:
            with self.subTest(file=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                deploy = source.split("\n  deploy:\n", 1)[1]
                for expected in (
                    "inputs.owner_approval == 'OWNER_APPROVED'",
                    "vars.MPW_BACKUP_RESTORE_VERIFIED == 'true'",
                    "vars.MPW_ROLLBACK_VERIFIED == 'true'",
                    "vars.MPW_TENANT_ISOLATION_VERIFIED == 'true'",
                ):
                    self.assertIn(expected, deploy)

    def test_approved_head_pin_precedes_access_to_any_production_ssh_secret(self):
        for name in SAFE_SUBSITES:
            with self.subTest(file=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                deploy = source.split("\n  deploy:\n", 1)[1]
                self.assertIn("release_sha:", source)
                self.assertIn("default: 'NO'", source)
                pin = deploy.index('[[ "$REQUESTED_RELEASE_SHA" == "$GITHUB_SHA" ]]')
                secret = deploy.index("secrets.")
                self.assertLess(pin, secret)

    def test_existing_farnaz_deployment_already_manual_only(self):
        source = (ROOT / ".github/workflows/mojplaywin-farnaz-deploy.yml").read_text(
            encoding="utf-8"
        )
        deploy = source.split("\n  deploy:\n", 1)[1]
        self.assertIn("github.event_name == 'workflow_dispatch'", deploy)
        self.assertNotIn("github.event_name == 'push' ||", deploy)


if __name__ == "__main__":
    unittest.main()
