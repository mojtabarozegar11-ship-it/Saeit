"""Offline safety contract for the owner-armed fresh MojPlayWin backup workflow.

This test never connects to cPanel/VPS and never reads or writes backup contents.
"""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/mpw-fresh-primary-backup-isolated-restore-20261101.yml"


class OwnerArmedBackupContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_dispatch_only_and_exact_owner_approval(self):
        s = self.source
        self.assertIn("  workflow_dispatch:", s)
        self.assertNotIn("\n  pull_request:", s)
        self.assertNotIn("\n  push:", s)
        for expected in (
            "github.actor == 'mojtabarozegar11-ship-it'",
            "github.ref == 'refs/heads/main'",
            "inputs.confirmation == 'BACKUP_AND_ISOLATED_RESTORE'",
            "github.repository == 'mojtabarozegar11-ship-it/Saeit'",
        ):
            self.assertIn(expected, s)

    def test_live_source_stays_readonly_and_pair_is_explicit(self):
        s = self.source
        self.assertLess(s.index("preflight-scoped-files"), s.index(" preflight-mysql") + 1)
        self.assertLess(s.index("preflight-mysql"), s.index("MYSQL_GPGV2_TRANSFER=started"))
        self.assertIn("MPW_BACKUP_SET_STEM=$MPW_BACKUP_SET_STEM", s)
        self.assertIn(" check-pair '$MPW_BACKUP_SET_STEM'", s)
        self.assertIn(" mysql-pair '$MPW_BACKUP_SET_STEM'", s)
        self.assertIn(" files-pair '$MPW_BACKUP_SET_STEM'", s)
        self.assertIn("python3 -B -c '$call' '$src64' files", s)
        self.assertIn("python3 -c '$call' '$src64' mysql", s)
        self.assertIn("VPS GPG AES256", s)
        self.assertIn("mpw_vps_backup_runtime_gate_readonly_20261101.py", s)
        self.assertIn("--require-ready", s)

    def test_isolated_restore_not_a_live_release(self):
        s = self.source
        self.assertIn("docker run -d --rm --name \"$label\" --network none", s)
        self.assertIn("MPW_RELEASE_PERMITTED=NO", s)
        self.assertIn("MPW_PASSENGER_DB_IDENTITY=NOT_PROVEN", s)
        self.assertIn("MPW_RECOVERY_KEY_OFF_VPS=NOT_VERIFIED", s)
        self.assertNotIn("manage.py migrate", s)
        self.assertNotIn("passenger_wsgi.py restart", s)

    def test_public_get_only_smoke_for_three_products(self):
        s = self.source
        for product_id in (72, 225, 879):
            self.assertIn(f"https://mojplaywin.com/store/product/{product_id}/checkout/", s)
        self.assertNotIn("curl -X POST", s)
        self.assertIn("TRX_PAYMENT_AND_PUBLIC_RELEASE=STILL_GATED_SEPARATELY", s)


if __name__ == "__main__":
    unittest.main()
