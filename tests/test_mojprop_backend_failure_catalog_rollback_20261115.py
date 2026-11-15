"""Regression: catalog must roll back if backend fails before smoke checks."""
from pathlib import Path
import unittest


class CatalogRollbackGateTests(unittest.TestCase):
    def test_backend_failure_triggers_catalog_rollback(self):
        workflow = Path(".github/workflows/mojprop-backend-controlled-release-20261115.yml").read_text(encoding="utf-8")
        rollback = workflow.split("- name: Roll back only Moj Prop route if deployment verification fails", 1)[1]
        gate = rollback.split("\n    needs:", 1)[0].split("\n      - name:", 1)[0]
        self.assertIn("steps.deploy.outcome == 'success'", gate)
        self.assertIn("steps.backend.outcome == 'failure'", gate)
        self.assertIn("steps.smoke.outcome == 'failure'", gate)
        self.assertIn("||", gate)


    def test_failed_install_also_attempts_manifest_guarded_backend_restore(self):
        workflow = Path(".github/workflows/mojprop-backend-controlled-release-20261115.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: Roll back Moj Prop backend on failed install or failed smoke", 1)[1]
        body = step.split("- name: Roll back only Moj Prop route", 1)[0]
        self.assertIn("steps.backend.outcome == 'failure'", body)
        self.assertIn("steps.smoke.outcome == 'failure'", body)
        self.assertIn("manifest.json", body)
        self.assertIn("rollback $GITHUB_RUN_ID", body)
        self.assertIn("NO_BACKEND_BACKUP_MANIFEST_TO_RESTORE", body)
        self.assertNotIn("github.event_name == 'push'", body)


if __name__ == "__main__":
    unittest.main()
