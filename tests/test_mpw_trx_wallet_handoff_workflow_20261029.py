"""Nonfinancial regression guards for MojPlayWin TRX handoff Actions workflow.

The workflow must never restart an unchanged Passenger app, and must recover an
interrupted SSH return after a successful source rename.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mpw-trx-wallet-handoff-publish-20261029.yml"
INSTALLER = ROOT / "scripts/mpw_trx_wallet_handoff_deploy_20261029.py"

class HandoffWorkflowSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.yaml = WORKFLOW.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")

    def test_noop_does_not_restart_or_rollback(self):
        self.assertIn("MPW_TRX_HANDOFF_ALREADY_APPLIED", self.yaml)
        self.assertIn("echo 'changed=false' >> \"$GITHUB_OUTPUT\"", self.yaml)
        self.assertIn("if: steps.install.outputs.changed == 'true'", self.yaml)
        self.assertIn("steps.install.outputs.changed == 'true'", self.yaml)
        self.assertIn("MPW_TRX_HANDOFF_ALREADY_APPLIED", self.installer)

    def test_failed_ssh_after_rename_arms_exact_rollback(self):
        self.assertIn("steps.install.outcome == 'failure'", self.yaml)
        self.assertIn("MPW_TRX_HANDOFF_ROLLBACK_OK", self.yaml)
        self.assertIn("MPW_TRX_HANDOFF_NOT_INSTALLED_BY_THIS_RUN", self.yaml)
        self.assertIn("MPW_TRX_HANDOFF_ROLLBACK_NOOP_NO_RESTART", self.yaml)
        self.assertIn("REFUSE_ROLLBACK_CONCURRENT_EDIT", self.installer)

    def test_checkout_and_invoice_smoke_remain(self):
        self.assertIn("Verify live-server invoice render without payment or order creation", self.yaml)
        self.assertIn("Verify protected storefront routes still work", self.yaml)
        self.assertIn("/store/product/", self.yaml)

if __name__ == "__main__":
    unittest.main()
