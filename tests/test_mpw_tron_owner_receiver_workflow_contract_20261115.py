"""Pinned live-readonly GitHub relay must not touch funds or expose keys."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/mpw-tron-owner-receiver-readonly-20261115.yml"
READER = ROOT / "scripts/mpw_tron_owner_wallet_live_readonly_20261115.py"


class LiveTRXOwnerReceiverWorkflowContractTests(unittest.TestCase):
    def test_merge_main_only_and_no_pull_request_secret_execution(self):
        s = WF.read_text("utf-8")
        self.assertIn("  push:", s)
        self.assertIn("    branches: [main]", s)
        self.assertIn("  workflow_dispatch:", s)
        self.assertNotIn("  pull_request:", s)
        self.assertIn("github.ref == 'refs/heads/main'", s)
        self.assertIn("permissions: {contents: read}", s)

    def test_pinned_relay_no_forwarding_or_shell_key_output(self):
        s = WF.read_text("utf-8")
        self.assertIn("SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs", s)
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04", s)
        self.assertIn("ForwardAgent no", s)
        self.assertIn("StrictHostKeyChecking yes", s)
        self.assertIn("BatchMode yes", s)
        self.assertIn("persist-credentials: false", s)
        self.assertIn("rm -rf -- \"$RUNNER_TEMP/mpw-tron-owner-readonly\"", s)
        self.assertNotIn("echo \"$VPS_KEY\"", s)
        self.assertNotIn("echo \"$HOST_KEY\"", s)

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
