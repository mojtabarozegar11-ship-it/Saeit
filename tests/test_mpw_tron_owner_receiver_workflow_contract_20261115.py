"""Pinned live-readonly GitHub relay must not touch funds or expose keys."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/mpw-tron-owner-receiver-readonly-20261115.yml"
READER = ROOT / "scripts/mpw_tron_owner_wallet_live_readonly_20261115.py"


class LiveTRXOwnerReceiverWorkflowContractTests(unittest.TestCase):
    def test_owner_issue_only_and_no_pr_secret_execution(self):
        s = WF.read_text("utf-8")
        self.assertNotIn("\n  push:", s)
        self.assertNotIn("\n  schedule:", s)
        self.assertNotIn("\n  workflow_dispatch:", s)
        self.assertIn("  pull_request:", s)
        self.assertIn("if: github.event_name == 'pull_request'", s)
        protected = s.split("  inspect-receiver:", 1)[1]
        self.assertIn("github.event_name == 'issue_comment'", protected)
        self.assertIn("github.ref == 'refs/heads/main'", protected)
        self.assertIn("github.event.comment.author_association == 'OWNER'", protected)
        self.assertIn("github.event.comment.body == 'MPW-TRON-OWNER-CURRENT-READONLY-20261115'", protected)
        self.assertIn("runs-on: [self-hosted, factory-vps]", protected)
        self.assertIn("permissions:\n  contents: read", s)

    def test_direct_cpanel_host_pin_no_vps_secret_or_forwarding(self):
        s = WF.read_text("utf-8")
        self.assertNotIn("SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs", s)
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04", s)
        self.assertIn("HostName 178.239.147.125", s)
        self.assertIn("Port 1396", s)
        self.assertNotIn("ProxyJump", s)
        self.assertNotIn("VPS_SSH_PRIVATE_KEY", s)
        self.assertIn("ForwardAgent no", s)
        self.assertIn("StrictHostKeyChecking yes", s)
        self.assertIn("BatchMode yes", s)
        self.assertIn("persist-credentials: false", s)
        self.assertIn("trap ", s)
        self.assertIn("rm -rf -- ", s)
        self.assertNotIn("echo \\"$VPS_KEY\\"", s)
        self.assertNotIn("echo \\"$HOST_KEY\\"", s)

    def test_script_not_allowed_to_send_chain_or_mutate_records(self):
        s = READER.read_text("utf-8")
        self.assertIn("def safe_report(", s)
        self.assertIn("def main():", s)
        self.assertIn("read_only", s)
        for bad in (
            "requests.post(", "urllib.request.urlopen(", "subprocess.run(",
            ".objects.create(", ".objects.update(", ".objects.delete(",
            ".save(", ".delete(", "broadcasttransaction", "private_key",
            "seed_phrase", "mnemonic", "wallet_balance",
        ):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, s)

    def test_only_boolean_host_receiver_match_no_sensitive_plaintext_output(self):
        s = READER.read_text("utf-8")
        self.assertIn('"owner_qr_receiver_match"', s)
        self.assertIn('"host_registry_matches_qr"', s)
        self.assertIn('"payment_finality_checked": False', s)
        self.assertIn('"customer_delivery_checked": False', s)
        self.assertNotIn("print(wallet)", s)
        self.assertNotIn("print(receiver)", s)
        self.assertNotIn("print(RECEIVERS)", s)
        self.assertNotIn("print(settings)", s)


if __name__ == "__main__":
    unittest.main()
