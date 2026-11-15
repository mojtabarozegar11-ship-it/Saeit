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


if __name__ == "__main__":
    unittest.main()
