"""Contract for the existing MojPlayWin financial evidence audit.

No cloud-to-VPS proxy or live cPanel interaction in this test suite.
Only checks reviewed workflow text and pinned security properties.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mpw-sales-intake-readonly-20261024.yml"
FP = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
OLD_IP = "178.239.147.125"


class SalesIntakeFactoryRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf8")
        cls.ssh = cls.source.split(
            "      - name: Establish fingerprint-pinned cPanel SSH directly from the factory runner\n", 1)[1].split(
            "      - name: Run read-only live sales and checkout audit\n", 1)[0]

    def test_reuses_existing_hourly_job_no_new_agent(self):
        self.assertIn("name: MojPlayWin visitor and support inbox read-only audit", self.source)
        self.assertIn("- cron: '21 * * * *'", self.source)
        self.assertIn("runs-on: [self-hosted, factory-vps]", self.source)
        self.assertNotIn("runs-on: ubuntu-latest", self.source)

    def test_direct_target_is_dns_proven_and_user_pinned(self):
        self.assertIn("HostName zohal.pws-dns.net", self.ssh)
        self.assertIn("User zomorod2", self.ssh)
        self.assertIn("Port 1396", self.ssh)
        self.assertIn("'test \"$(id -un)\" = \"zomorod2\"'", self.ssh)
        self.assertNotIn(OLD_IP, self.ssh)

    def test_no_proxy_or_vps_secret_in_direct_connection(self):
        self.assertNotIn("VPS_KEY", self.ssh)
        self.assertNotIn("VPS_SSH_PRIVATE_KEY", self.ssh)
        self.assertNotIn("ProxyJump", self.ssh)
        self.assertNotIn("ssh -F \"$d/config\" saeit-vps", self.ssh)
        self.assertIn("secrets.SAEIT_HOST_SSH_PRIVATE_KEY", self.ssh)

    def test_hostname_fingerprint_fails_closed(self):
        self.assertIn(FP, self.ssh)
        self.assertIn('actual_pin="$(ssh-keygen -lf', self.ssh)
        self.assertIn('if test "$actual_pin" != "' + FP + '"; then', self.ssh)
        self.assertIn("MPW_CPANEL_READONLY_HOST_KEY_MISMATCH", self.ssh)
        self.assertIn("test -s \"$d/host.candidate\"", self.ssh)

    def test_pinned_identity_safeguards_are_not_downgraded(self):
        for setting in (
            "StrictHostKeyChecking yes",
            "IdentitiesOnly yes",
            "BatchMode yes",
            "ConnectionAttempts 1",
            "ForwardAgent no",
            "RequestTTY no",
            "UserKnownHostsFile $d/host.known",
        ):
            self.assertIn(setting, self.ssh)
        self.assertNotIn("StrictHostKeyChecking no", self.ssh)
        self.assertNotIn("UserKnownHostsFile=/dev/null", self.ssh)

    def test_django_inventory_is_never_posted_or_run_for_writes(self):
        self.assertIn("ssh -T -F \"$d/config\"", self.source)
        self.assertEqual(self.source.count('3.11/bin/python -B -"'), 7)
        self.assertNotIn("3.11/bin/python -\"", self.source)
        self.assertNotIn("manage.py migrate", self.source)
        self.assertNotIn("curl -X POST", self.source)
        self.assertNotIn("git push", self.source)

    def test_paid_provenance_is_distinct_from_purchase(self):
        self.assertIn("Join paid flags to finalized receipts and fulfillment (read only)", self.source)
        self.assertIn("scripts/mpw_paid_provenance_readonly_20261105.py", self.source)
        self.assertIn("scripts/mpw_payment_cron_heartbeat_readonly.py", self.source)
        self.assertIn("scripts/mpw_payment_100_live_baseline_readonly_20261021.py", self.source)
        self.assertNotIn("invoices_created=1", self.source)

    def test_ssh_key_never_leaves_temp_and_is_cleaned_up(self):
        self.assertIn('umask 077', self.ssh)
        self.assertIn('chmod 600 "$d/host.key"', self.ssh)
        self.assertIn('chmod 600 "$d/config"', self.ssh)
        self.assertIn('name: Remove local SSH material', self.source)
        self.assertIn('if: always()', self.source)
        self.assertIn('rm -rf -- "$RUNNER_TEMP/mpw-sales-audit-ssh"', self.source)

    def test_access_failure_cannot_be_reported_as_sales_success(self):
        first = self.source.split(
            "      - name: Run read-only live sales and checkout audit\n", 1)[1].split(
            "      - name: Check payment reconciler heartbeat", 1)[0]
        self.assertIn("set -euo pipefail", first)
        self.assertIn("timeout 150s ssh -T", first)
        self.assertNotIn("continue-on-error: true", first)


if __name__ == "__main__":
    unittest.main()
