"""Verify real backend release archive contains every file its installer reads.

Fail the source release review if a signed-receipt import is missing from the
package even when the checked-out GitHub source has the Python module.
No archive is uploaded, no mainnet activity and no production deploy.
"""
import shlex
import unittest
from pathlib import Path

from scripts.deploy_mojplaywin_moj_prop_backend import ALL_FILES


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mojprop-backend-controlled-release-20261115.yml"


def staged_tar_paths():
    text = WORKFLOW.read_text(encoding="utf-8")
    step = text.split("- name: Package only Moj Prop installer and page", 1)[1]
    command = next(line.strip() for line in step.splitlines()
                   if line.strip().startswith("run: tar -cf "))
    argv = shlex.split(command.removeprefix("run: "))
    if len(argv) < 4 or argv[:2] != ["tar", "-cf"]:
        raise AssertionError("unexpected release archive invocation")
    return set(argv[3:])


class MojPropReleasePackageTests(unittest.TestCase):
    def test_installer_files_are_in_actual_staged_tar(self):
        paths = staged_tar_paths()
        for item in ALL_FILES:
            with self.subTest(file=str(item)):
                self.assertIn(str(item), paths)
                self.assertTrue((ROOT / item).is_file())

    def test_signed_receipt_dependency_is_installed_and_packaged(self):
        paths = staged_tar_paths()
        self.assertIn("core/mojprop_receipts.py", paths)
        self.assertIn("core/mojprop_views.py", paths)
        view = (ROOT / "core/mojprop_views.py").read_text(encoding="utf-8")
        self.assertIn("from .mojprop_receipts import", view)

    def test_source_only_ci_cannot_dispatch_backend_deploy(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        header = workflow.split("\njobs:\n", 1)[0]
        self.assertIn("  workflow_dispatch:\n", header)
        self.assertNotIn("  push:\n", header)
        self.assertNotIn("  pull_request:\n", header)
        deploy = workflow.split("\n  deploy:\n", 1)[1]
        self.assertIn("github.event_name == 'workflow_dispatch'", deploy)
        self.assertIn("vars.MOJPROP_BACKUP_RESTORE_VERIFIED == 'true'", deploy)
        self.assertIn("vars.MOJPROP_TENANT_ISOLATION_VERIFIED == 'true'", deploy)


if __name__ == "__main__":
    unittest.main()
