"""The live wallet auditor may ONLY run from the owner-authorized factory runner."""
from __future__ import annotations
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mpw-tron-owner-receiver-readonly-20261115.yml"
SCRIPT = ROOT / "scripts/mpw_tron_owner_wallet_live_readonly_20261115.py"
MARKER = "MPW-TRON-OWNER-CURRENT-READONLY-20261115"
REVIEWED_BLOB = "b194580753fbf18994ea8752e3cd39a3a25b2e57"


def blob_sha(path):
    data = path.read_bytes()
    header = ("blob %d\0" % len(data)).encode()
    return hashlib.sha1(header + data).hexdigest()


class OwnerReceiverFactoryRunContract(unittest.TestCase):
    def setUp(self):
        self.yaml = WORKFLOW.read_text(encoding="utf8")
        self.python = SCRIPT.read_text(encoding="utf8")

    def test_source_blob_pinned(self):
        self.assertEqual(blob_sha(SCRIPT), REVIEWED_BLOB)
        self.assertIn(REVIEWED_BLOB, self.yaml)

    def test_no_production_write_on_main_push(self):
        self.assertNotIn("\n  push:", self.yaml)

    def test_no_schedule(self):
        self.assertNotIn("\n  schedule:", self.yaml)

    def test_no_workflow_dispatch(self):
        self.assertNotIn("\n  workflow_dispatch:", self.yaml)

    def test_no_workflow_run(self):
        self.assertNotIn("\n  workflow_run:", self.yaml)

    def test_private_issue_owner_only(self):
        self.assertIn("github.event.issue.number == 1600", self.yaml)
        self.assertIn("github.event.comment.author_association == 'OWNER'", self.yaml)
        self.assertIn("github.event.comment.user.login == 'mojtabarozegar11-ship-it'", self.yaml)
        self.assertIn("github.actor == 'mojtabarozegar11-ship-it'", self.yaml)

    def test_marker_scoped_to_owner_comment(self):
        self.assertIn("github.event.comment.body == '" + MARKER + "'", self.yaml)
        self.assertEqual(self.yaml.count(MARKER), 1)

    def test_no_pr_host_write(self):
        self.assertIn("github.event_name == 'issue_comment'", self.yaml)
        self.assertIn("!github.event.issue.pull_request", self.yaml)

    def test_exact_main_branch_only(self):
        self.assertIn("github.ref == 'refs/heads/main'", self.yaml)

    def test_runner_is_previously_verified_local_factory(self):
        self.assertIn("runs-on: [self-hosted, factory-vps]", self.yaml)

    def test_exact_cpanel_ip_port_only(self):
        self.assertIn("HostName 178.239.147.125", self.yaml)
        self.assertIn("Port 1396", self.yaml)
        self.assertNotIn("zohal.pws-dns.net", self.yaml)
        self.assertNotIn("ProxyJump", self.yaml)
        self.assertNotIn("VPS_SSH_PRIVATE_KEY", self.yaml)

    def test_pinned_host_key_fingerprint(self):
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04", self.yaml)
        self.assertIn("StrictHostKeyChecking yes", self.yaml)
        self.assertIn("ForwardAgent no", self.yaml)

    def test_identity_required_on_remote_host(self):
        self.assertIn('test "$(id -un)" = "zomorod2"', self.yaml)
        self.assertIn("passenger_wsgi.py", self.yaml)

    def test_remote_python_never_stores_bytecode(self):
        self.assertIn("/bin/python -B -", self.yaml)

    def test_no_money_or_mutation_commands(self):
        step = self.yaml.split("      - name: Inspect effective current MojPlayWin TRON receiver", 1)[1]
        for needle in ("sudo ", "scp ", "rsync ", "manage.py migrate", "docker run",
                       "broadcasttransaction", "sendrawtransaction", "curl -X POST",
                       "git push", "pip install", "chmod 777", "manage.py shell"):
            self.assertNotIn(needle, step)

    def test_report_not_falsely_claiming_received_funds(self):
        self.assertIn('d["live_sale_verified"] is False', self.yaml)
        self.assertIn('d["payment_finality_checked"] is False', self.yaml)
        self.assertIn('d["customer_delivery_checked"] is False', self.yaml)

    def test_probe_never_reads_or_prints_full_wallet_secret(self):
        self.assertIn('"read_only": True', self.python)
        self.assertNotIn("private_key", self.python)
        self.assertNotIn("mnemonic", self.python)
        self.assertNotIn("objects.create(", self.python)

    def test_report_bound_to_exact_owner_qr(self):
        self.assertIn('merchant_record.get("recipient") == OWNER_QR', self.python)
        self.assertIn('"host_registry_matches_qr"', self.python)

    def test_only_source_checks_run_on_pull_request(self):
        self.assertIn("if: github.event_name == 'pull_request'", self.yaml)
        self.assertIn("github.event.comment.body == '" + MARKER + "'", self.yaml)


if __name__ == "__main__":
    unittest.main()
