"""Unit tests run only with synthetic temporary paths; no server writes."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_backup_vps_destination_readonly import probe


class BackupDestinationPrerequisiteTests(unittest.TestCase):
    def test_vps_does_not_claim_safe_backup_destination(self):
        with tempfile.TemporaryDirectory() as td:
            result = probe("vps", home=Path(td))
            self.assertTrue(result["home_directory"]["exists"])
            self.assertFalse(result["backup_storage_root_confirmed"])
            self.assertFalse(result["backup_destination_approved_safe"])
            self.assertFalse(result["backup_written"])
            self.assertFalse(result["release_permitted"])
            self.assertNotIn(td, json.dumps(result))

    def test_cpanel_does_not_claim_full_tenant_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app").mkdir()
            (root / "childsite").mkdir()
            (root / "private").write_text("secret")
            report = probe("cpanel", home=root)
            self.assertTrue(report["account_direct_child_inventory"]["readable"])
            self.assertEqual(report["account_direct_child_inventory"]["subdirectories"], 2)
            self.assertFalse(report["full_tenant_media_db_inventory_complete"])
            self.assertFalse(report["active_database_connection_verified"])
            self.assertNotIn("childsite", str(report))
            self.assertNotIn("private", str(report))
            self.assertFalse(report["backup_written"])

    def test_targets_fail_closed(self):
        with self.assertRaises(ValueError):
            probe("production-backup")


if __name__ == "__main__":
    unittest.main()
