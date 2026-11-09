"""Read-only contracts for the staging SSH diagnostic pinning repair."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / ".github/workflows/staging-ssh-diagnostics.yml"
RELAY = ROOT / ".github/workflows/zomorod-private-command-dispatch.yml"
EXPECTED_FP = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"


class StagingSshPinTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diag = DIAGNOSTIC.read_text(encoding="utf-8")
        cls.relay = RELAY.read_text(encoding="utf-8")
        diag_match = re.search(r"known='([^']+)'", cls.diag)
        relay_line = next(line for line in cls.relay.splitlines()
                          if ' > "$d/vps.known"' in line)
        relay_match = re.search(r"'(178\.239\.147\.150 ssh-rsa [^']+)'", relay_line)
        assert diag_match and relay_match
        cls.fallback_key = diag_match.group(1)
        cls.relay_key = relay_match.group(1)

    def test_offline_public_pin_is_identical_to_private_relay(self):
        self.assertEqual(self.fallback_key, self.relay_key)

    def test_pinned_fingerprint_matches_real_key(self):
        if not shutil.which("ssh-keygen"):
            self.skipTest("ssh-keygen unavailable")
        run = subprocess.run(["ssh-keygen", "-lf", "-", "-E", "sha256"],
                             input=self.fallback_key + "\n", text=True,
                             capture_output=True, check=True)
        self.assertIn(EXPECTED_FP, run.stdout)

    def test_no_live_keyscan_dependency(self):
        self.assertNotIn("ssh-keyscan", self.diag)

    def test_errors_are_explicit_and_fail_closed(self):
        self.assertIn("VPS_PINNED_KEY=INVALID", self.diag)
        self.assertIn("VPS_PINNED_KEY=MISMATCH", self.diag)
        self.assertIn('if ! fingerprint_output=', self.diag)

    def test_secret_known_hosts_also_must_match_pin(self):
        self.assertIn('if [[ "$TARGET" == vps ]]; then', self.diag)
        self.assertIn('if [[ -z "$known" ]]; then', self.diag)
        self.assertIn('fingerprint_output', self.diag)

    def test_job_is_manual_readonly_only(self):
        self.assertIn("  workflow_dispatch:", self.diag)
        self.assertNotIn("  schedule:", self.diag)
        self.assertNotIn("  push:", self.diag)
        self.assertIn("  contents: read", self.diag)

    def test_ssh_host_key_is_strict_and_no_agent_forwarding(self):
        self.assertIn("StrictHostKeyChecking=yes", self.diag)
        self.assertIn("BatchMode=yes", self.diag)
        self.assertNotIn("StrictHostKeyChecking=no", self.diag)
        self.assertNotIn("ForwardAgent=yes", self.diag)

    def test_allowlisted_readonly_checks_are_preserved(self):
        self.assertIn("options: [identity, staging_directory, staging_processes]", self.diag)
        self.assertIn("*) exit 1 ;;", self.diag)
        self.assertNotIn("sudo ", self.diag)

if __name__ == "__main__":
    unittest.main()
