"""S-01 checkout relay acceptance: static fail-closed checks; no network calls."""
import unittest
from pathlib import Path

WORKFLOW = (Path(__file__).resolve().parents[1] / ".github/workflows" /
            "mpw-checkout-csp-readonly-preflight-20261029.yml").read_text(encoding="utf-8")


class PinnedRelayRegressionTests(unittest.TestCase):
    def test_only_existing_two_hop_relay(self):
        self.assertIn("ProxyJump saeit-vps", WORKFLOW)
        self.assertIn("HostName 178.239.147.150", WORKFLOW)
        self.assertIn("HostName 178.239.147.125", WORKFLOW)
        self.assertNotIn("saeit-cpanel-direct", WORKFLOW)
        self.assertIn("StrictHostKeyChecking yes", WORKFLOW)
        self.assertIn("ForwardAgent no", WORKFLOW)

    def test_reuses_proven_staging_handshake_parameters(self):
        self.assertIn("ControlPath $d/cpanel.sock", WORKFLOW)
        self.assertIn("ConnectTimeout 30", WORKFLOW)
        self.assertIn("ConnectionAttempts 3", WORKFLOW)
        self.assertIn("ServerAliveInterval 15", WORKFLOW)
        self.assertIn("ServerAliveCountMax 4", WORKFLOW)
        self.assertIn("-o ConnectTimeout=25 -o ConnectionAttempts=1 saeit-cpanel", WORKFLOW)

    def test_no_separate_early_vps_connection(self):
        self.assertNotIn('ssh -T -F "$d/config" saeit-vps \'true\'', WORKFLOW)
        self.assertIn("S01_VPS_READONLY_SESSION=VERIFIED_VIA_PINNED_PROXYJUMP", WORKFLOW)
        self.assertIn('test "$(id -un)" = "zomorod2"', WORKFLOW)

    def test_readonly_and_no_release_claim(self):
        self.assertIn("S01_PROVENANCE_RELEASE_AUTHORIZATION=BLOCKED", WORKFLOW)
        self.assertIn("S01_PINNED_SESSION=BLOCKED", WORKFLOW)
        self.assertNotIn("systemctl restart", WORKFLOW)
        self.assertNotIn("factory-worker", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
