import datetime as dt
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/f01_offhost_destination_decision_20261030.py"
spec = importlib.util.spec_from_file_location("gate", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

NOW = dt.datetime(2026, 10, 30, 0, 28, 30, tzinfo=dt.timezone.utc)
SOURCE = {
    "schema": "f01-backup-source-inventory.v1",
    "status": "INSPECT_ONLY", "read_only": True, "truncated": False,
    "observed_utc": "2026-10-30T00:28:20+00:00",
    "newest_three_metadata_only": [
        {"bytes": 1396473856, "mtime_utc": "2026-10-28T01:05:09+00:00"}],
    "database_consistency_verified": False,
    "offhost_backup_exists_verified": False, "restore_verified": False,
}
DEST = {
    "account_quota_evidence": "INDEPENDENTLY_VERIFIED",
    "same_destination_account": True,
    "observed_utc": "2026-10-30T00:28:20+00:00",
    "account_free_bytes": 10 * 1024 ** 3,
}

class FailClosedGate(unittest.TestCase):
    def test_missing_account_quota(self):
        self.assertEqual(gate.assess(SOURCE, now=NOW)["status"], "BLOCKED")
    def test_shared_filesystem_not_account_quota(self):
        s = dict(SOURCE, root_total_free_bytes_including_privileged=999999999999)
        self.assertFalse(gate.assess(s, now=NOW)["capacity_sizing_passed"])
    def test_insufficient_account_free(self):
        d = dict(DEST, account_free_bytes=1396473856)
        self.assertEqual(gate.assess(SOURCE, d, NOW)["status"], "BLOCKED")
    def test_stale_existing_snapshot(self):
        result = gate.assess(SOURCE, DEST, NOW)
        self.assertIn("SNAPSHOT_OLDER_THAN_24_HOURS", result["reasons"])
        self.assertFalse(result["capacity_sizing_passed"])
    def test_fresh_sizing_never_authorizes_transfer(self):
        s = dict(SOURCE, newest_three_metadata_only=[
            {"bytes": 1396473856, "mtime_utc": "2026-10-30T00:20:00+00:00"}])
        result = gate.assess(s, DEST, NOW)
        self.assertTrue(result["capacity_sizing_passed"])
        self.assertFalse(result["transfer_authorized"])
        self.assertFalse(result["reboot_authorized"])
    def test_boolean_quota_rejected(self):
        d = dict(DEST, account_free_bytes=True)
        self.assertEqual(gate.assess(SOURCE, d, NOW)["status"], "BLOCKED")
    def test_stale_quota_rejected(self):
        d = dict(DEST, observed_utc="2026-10-29T00:00:00+00:00")
        self.assertEqual(gate.assess(SOURCE, d, NOW)["status"], "BLOCKED")
    def test_future_inventory_rejected(self):
        s = dict(SOURCE, observed_utc="2026-10-31T00:00:00+00:00")
        self.assertEqual(gate.assess(s, DEST, NOW)["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
