"""Fail-closed master activation workflow policy. No production access or writes."""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/vps-master-agent-activate.yml"


class MasterWorkflowReleaseGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_activation_only_with_explicit_approval(self):
        s = self.text
        self.assertIn("workflow_dispatch:", s)
        self.assertIn("recovery_authorized:", s)
        self.assertIn("default: false", s)
        self.assertIn(
            "if: github.event_name == 'workflow_dispatch' && inputs.recovery_authorized == true",
            s,
        )
        self.assertNotIn("github.event_name != 'pull_request'", s)

    def test_remote_disk_gate_precedes_all_remote_writes(self):
        s = self.text
        gate = s.index("MASTER_REMOTE_PREFLIGHT_ENOSPC_BLOCKED")
        remote_install = s.index("ssh \"\u0024{opts[@]}\" githubops@178.239.147.150 'install -d")
        scp = s.index("scp \"\u0024{opts[@]}\"")
        extract = s.index("target.write_bytes(")
        self.assertLess(gate, remote_install)
        self.assertLess(gate, scp)
        self.assertLess(gate, extract)
        self.assertIn("required=5*1024**3+128*1024**2", s)
        self.assertIn("raise SystemExit(75)", s)

    def test_ssh_pinning_and_single_writer_unchanged(self):
        s = self.text
        self.assertIn("StrictHostKeyChecking=yes", s)
        self.assertIn("vps-single-master-activation", s)
        self.assertIn("cancel-in-progress: false", s)


if __name__ == "__main__":
    unittest.main()
