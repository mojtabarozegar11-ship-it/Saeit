"""Fail-closed master activation workflow policy. No production access or writes."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap
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
        extract = s.index("fd=os.open(temporary,")
        self.assertLess(gate, remote_install)
        self.assertLess(gate, scp)
        self.assertLess(gate, extract)
        self.assertIn("required=5*1024**3+128*1024**2", s)
        self.assertIn("raise SystemExit(75)", s)

    def test_linked_stage_ancestor_blocks_before_remote_writes(self):
        s = self.text
        self.assertLess(s.index("MASTER_REMOTE_PREFLIGHT_LINKED_STAGE_BLOCKED"),
                        s.index("ssh \"\u0024{opts[@]}\" githubops@178.239.147.150 'install -d"))
        start = "python3 - <<'PREFLIGHT'\n"
        self.assertIn(start, s)
        program = textwrap.dedent(
            s.split(start, 1)[1].split("\n          PREFLIGHT", 1)[0])
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / "factory-runtime"
            base.mkdir()
            destination = Path(root) / "outside"
            destination.mkdir()
            (base / "operations").symlink_to(destination, target_is_directory=True)
            result = subprocess.run(
                [sys.executable, "-B", "-c", program],
                env={**os.environ, "HOME": root},
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 76, result.stderr)
            self.assertIn("MASTER_REMOTE_PREFLIGHT_LINKED_STAGE_BLOCKED",
                          result.stdout)

    def test_staging_is_atomic_and_rejects_links(self):
        s = self.text
        for token in ("MASTER_STAGE_ROOT_UNSAFE", "MASTER_STAGE_LINKED_PARENT_REJECTED",
                      "MASTER_STAGE_LINKED_TARGET_REJECTED", "os.replace(temporary,target)"):
            self.assertIn(token, s)
        self.assertNotIn("target.write_bytes(", s)
        self.assertIn("any(part.is_symlink() for part in (root, *root.parents))", s)
        self.assertLess(s.index("MASTER_STAGE_ROOT_UNSAFE"),
                        s.index("fd=os.open(temporary,"))

    def test_ssh_pinning_and_single_writer_unchanged(self):
        s = self.text
        self.assertIn("StrictHostKeyChecking=yes", s)
        self.assertIn("vps-single-master-activation", s)
        self.assertIn("cancel-in-progress: false", s)


if __name__ == "__main__":
    unittest.main()
