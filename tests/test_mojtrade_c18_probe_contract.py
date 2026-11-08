"""C18 inspection workflow must never receive credentials or execute orders."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = (ROOT / ".github/workflows/mojtrade-c18-vps-transport-probe.yml").read_text(
    encoding="utf-8")


class TransportProbeContractTests(unittest.TestCase):
    def test_one_shot_own_repo_pr_only(self):
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", PROBE)
        self.assertIn("github.head_ref == 'fix/mojtrade-c18-vps-transport-probe-20261108'", PROBE)
        self.assertNotIn("workflow_dispatch:", PROBE)
        self.assertNotIn("schedule:", PROBE)

    def test_read_only_network_not_a_secret_or_login_workflow(self):
        self.assertIn("socket.create_connection", PROBE)
        self.assertIn("ssh-keyscan -T 8 -t rsa", PROBE)
        self.assertIn("MOJTRADE_C18_HOST_KEY_MISMATCH_STOP", PROBE)
        for forbidden in ("secrets.", "ssh -i", "scp ", "rsync", "curl -X POST",
                          "ExecuteMarketOrder", "MOJTRADE_RISK_TOKEN", "sudo ",
                          "write-token", "--enable-demo-reservations"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, PROBE)

    def test_default_job_has_no_elevated_rights(self):
        self.assertIn("permissions:\n  contents: read", PROBE)
        self.assertIn("timeout-minutes: 2", PROBE)
        self.assertIn("EXPECTED_RSA_FINGERPRINT", PROBE)


if __name__ == "__main__":
    unittest.main()
