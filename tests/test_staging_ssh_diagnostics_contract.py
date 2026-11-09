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

    def _process_script(self):
        row = next(line for line in self.diag.splitlines()
                   if "staging_processes) remote=" in line)
        return row.split("remote='", 1)[1].rsplit("' ;;", 1)[0]

    def test_staging_process_mode_cannot_print_command_arguments(self):
        self.assertNotIn("pid,comm,args", self.diag)
        self.assertNotIn("cut -c1-180", self.diag)
        self.assertIn("STAGING_FACTORY_COUNT", self.diag)
        self.assertIn("STAGING_LOOP_COUNT", self.diag)

    def test_staging_processes_emit_counts_not_secrets(self):
        mock = 'ps() { printf "%s\n" "python3 factory_staging_tick --token=SECRET_ALPHA" "python3 stage1_10s_loop --password=SECRET_BETA"; }; '
        run = subprocess.run(["bash", "-c", mock + self._process_script()],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.splitlines(),
                         ["STAGING_FACTORY_COUNT=1", "STAGING_LOOP_COUNT=1"])
        self.assertNotIn("SECRET_ALPHA", run.stdout)
        self.assertNotIn("SECRET_BETA", run.stdout)

    def test_unavailable_process_readback_fails_closed(self):
        run = subprocess.run(["bash", "-c",
                              "ps() { return 2; }; " + self._process_script()],
                             capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(run.stdout.strip(), "STAGING_PROCESS_READBACK=UNAVAILABLE")

    def test_no_matching_staging_processes_returns_zero_counts(self):
        mock = 'ps() { printf "%s\n" "bash --password=SECRET_OTHER"; }; '
        run = subprocess.run(["bash", "-c", mock + self._process_script()],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.splitlines(),
                         ["STAGING_FACTORY_COUNT=0", "STAGING_LOOP_COUNT=0"])
        self.assertNotIn("SECRET_OTHER", run.stdout)

if __name__ == "__main__":
    unittest.main()
