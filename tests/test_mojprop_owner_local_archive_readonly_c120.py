"""C120 local cPanel backup locator: no data content, writing or PII."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.mojprop_owner_local_archive_readonly_c120 import (
    scan_fixed_home_metadata, inspect, MAX_ENTRIES,
)


FILE = "backup-11.16.2026_15-09-11_zomorod2.tar.gz"


class LocalBackupMetadataC120Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.uid = os.geteuid()

    def make(self, name=FILE):
        path = self.home / name
        path.write_bytes(b"0" * 1024)
        path.chmod(0o600)
        return path

    def test_01_valid_owner_backup_is_only_candidate_not_restore(self):
        self.make()
        out = scan_fixed_home_metadata(self.home, uid=self.uid)
        self.assertTrue(out["home_metadata_scan_completed"])
        self.assertEqual(out["local_archive_candidates_count"], 1)
        self.assertTrue(out["safe_owner_regular_file_metadata"])
        self.assertNotIn("backup-11", str(out))

    def test_02_empty_home_is_scanned_successfully_no_candidates(self):
        out = scan_fixed_home_metadata(self.home, uid=self.uid)
        self.assertTrue(out["home_metadata_scan_completed"])
        self.assertEqual(out["local_archive_candidates_count"], 0)

    def test_03_wrong_filename_and_buyer_secrets_never_scanned_as_archive(self):
        for filename in ("backup-buyer-email.tar.gz", "customer@example.org",
                         "archive.tar.gz", ".env", "full-database.sql.gz"):
            self.make(filename)
        out = scan_fixed_home_metadata(self.home, uid=self.uid)
        self.assertEqual(out["local_archive_candidates_count"], 0)
        self.assertNotIn("customer@", str(out))

    def test_04_symlink_backup_filename_never_followed(self):
        existing = self.make("untrusted-private-material")
        (self.home / FILE).symlink_to(existing)
        out = scan_fixed_home_metadata(self.home, uid=self.uid)
        self.assertTrue(out["home_metadata_scan_completed"])
        self.assertEqual(out["local_archive_candidates_count"], 0)

    def test_05_hardlinked_archive_avoids_second_write_location(self):
        existing = self.make()
        os.link(existing, self.home / "hardlink")
        out = scan_fixed_home_metadata(self.home, uid=self.uid)
        self.assertEqual(out["local_archive_candidates_count"], 0)

    def test_06_group_readable_backup_metadata_is_excluded(self):
        candidate = self.make()
        candidate.chmod(0o640)
        out = scan_fixed_home_metadata(self.home, uid=self.uid)
        self.assertEqual(out["local_archive_candidates_count"], 0)

    def test_07_undersized_archive_is_never_considered_available(self):
        candidate = self.make()
        candidate.write_bytes(b"too small")
        out = scan_fixed_home_metadata(self.home, uid=self.uid)
        self.assertEqual(out["local_archive_candidates_count"], 0)

    def test_08_home_directory_symlink_denied_without_scan(self):
        link = self.home / "home-link"
        link.symlink_to(self.home, target_is_directory=True)
        out = scan_fixed_home_metadata(link, uid=self.uid)
        self.assertFalse(out["home_metadata_scan_completed"])

    def test_09_wrong_home_owner_denied_without_scan(self):
        out = scan_fixed_home_metadata(self.home, uid=self.uid+1)
        self.assertFalse(out["home_metadata_scan_completed"])

    def test_10_unsafe_world_writable_home_denied(self):
        oldmode = stat.S_IMODE(self.home.stat().st_mode)
        try:
            self.home.chmod(0o777)
            out = scan_fixed_home_metadata(self.home, uid=self.uid)
            self.assertFalse(out["home_metadata_scan_completed"])
        finally:
            self.home.chmod(oldmode)

    def test_11_fixed_process_owner_check_precedes_home_scan(self):
        from scripts import mojprop_owner_local_archive_readonly_c120 as mod
        with patch.object(mod.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name="wrong-user")), \
             patch.object(mod, "scan_fixed_home_metadata") as scan:
            out = inspect()
        self.assertFalse(out["owner_identity_verified"])
        scan.assert_not_called()

    def test_12_even_found_archives_cannot_authorize_any_release(self):
        from scripts import mojprop_owner_local_archive_readonly_c120 as mod
        with patch.object(mod.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name="zomorod2")), \
             patch.object(mod, "HOME", self.home):
            self.make()
            out = inspect()
        self.assertEqual(out["local_archive_candidates_count"], 1)
        for key in ("local_archive_content_read", "archive_downloaded",
                    "app_or_db_accessed", "customer_data_accessed",
                    "independent_encrypted_full_restore_proven",
                    "provider_offhost_backup_verified",
                    "production_deployment_authorized", "new_cost_incurred"):
            self.assertIs(out[key], False)
