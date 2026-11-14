"""Offline regression tests for bounded, credential-free SSH transport diagnosis."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/zomorod_vps_transport_diagnostic_readonly_20261114.py"
SPEC = importlib.util.spec_from_file_location("zm_transport_diagnostic", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class TransportDiagnosticTests(unittest.TestCase):
    def test_tcp_blocked_skips_ssh(self):
        def forbidden():
            raise AssertionError("ssh scan attempted without TCP")
        r = MOD.diagnose(lambda: False, forbidden)
        self.assertEqual(r["status"], "tcp22_unreachable_or_filtered")
        self.assertFalse(r["tcp22_open"])

    def test_tcp_and_rsa_is_unverified(self):
        r = MOD.diagnose(lambda: True, lambda: {"rsa"})
        self.assertEqual(r["status"], "tcp22_open_rsa_observed_unverified")
        self.assertFalse(r["host_fingerprint_verified"])

    def test_only_ed25519_does_not_claim_vps_offline(self):
        r = MOD.diagnose(lambda: True, lambda: {"ed25519"})
        self.assertEqual(r["status"], "tcp22_open_only_ed25519_observed")
        self.assertTrue(r["tcp22_open"])

    def test_tcp_without_keys(self):
        self.assertEqual(MOD.diagnose(lambda: True, lambda: set())["status"], "tcp22_open_no_host_key_observed")

    def test_two_key_types_not_equivalent_to_trust(self):
        r = MOD.diagnose(lambda: True, lambda: {"rsa", "ed25519"})
        self.assertTrue(r["ed25519_observed"])
        self.assertFalse(r["host_fingerprint_verified"])

    def test_keyscan_timeout_fails_closed(self):
        with patch.object(MOD.subprocess, "run", side_effect=subprocess.TimeoutExpired("ssh-keyscan", 8)):
            self.assertEqual(MOD.observed_key_types(), set())

    def test_keyscan_output_parsed_without_leaking_material(self):
        stdout = "178.239.147.150 ssh-rsa AAAASAMPLEKEY\n# ignored\n"
        with patch.object(MOD.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=stdout, stderr="secret")) as runner:
            self.assertEqual(MOD.observed_key_types(), {"rsa"})
        self.assertTrue(runner.call_args.kwargs["capture_output"])
        self.assertEqual(runner.call_args.args[0][0], "ssh-keyscan")

    def test_no_remote_writes_authentication_or_secrets(self):
        for connected in (True, False):
            r = MOD.diagnose(lambda: connected, lambda: {"rsa"})
            self.assertEqual(r["site_writes"], 0)
            self.assertEqual(r["authentication_attempts"], 0)
            self.assertFalse(r["secrets_used"])
            self.assertFalse(r["cpanel_connectivity_verified"])
            self.assertFalse(r["active_php_verified"])

    def test_only_fixed_existing_target(self):
        self.assertEqual((MOD.HOST, MOD.PORT), ("178.239.147.150", 22))

if __name__ == "__main__":
    unittest.main()
