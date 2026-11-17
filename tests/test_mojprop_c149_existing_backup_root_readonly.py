"""C149 adversarial bounded metadata-only owner backup inventory tests."""
from __future__ import annotations

import builtins
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c149_existing_backup_root_readonly as module


def safe_root(parent):
    root=Path(parent)
    os.chmod(root,0o700)
    return root


def make_file(path):
    path.write_bytes(b"synthetic, noncustomer test only")
    os.chmod(path,0o600)


class OwnerExistingBackupRootTests(unittest.TestCase):
    def test_01_empty_safe_root_reports_zero_candidates_not_restore(self):
        with tempfile.TemporaryDirectory() as td:
            x=module.scan_fixed_backup_root(safe_root(td),os.geteuid())
        self.assertTrue(x["scan_completed"])
        self.assertTrue(x["root_safe"])
        self.assertEqual(x["direct_entries_scanned"],0)
        self.assertEqual(x["owner_private_regular_archives"],0)
        self.assertFalse(x["independent_full_app_db_media_restore_proven"])

    def test_02_owner_regular_archive_metadata_is_candidate_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            make_file(root/"opaque-contents.tar.gz")
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertEqual(x["owner_private_regular_archives"],1)
        self.assertFalse(x["restore_rehearsal_verified"])
        self.assertFalse(x["backup_content_read"])

    def test_03_fixed_top_level_manifest_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            make_file(root/"manifest.json")
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertEqual(x["owner_private_manifest_metadata_files"],1)
        self.assertEqual(x["matched_run_dirs_with_manifest_metadata"],0)

    def test_04_known_run_directory_manifest_stat_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            run=root/"44000000012"
            run.mkdir(mode=0o700)
            make_file(run/"predeploy-manifest.json")
            make_file(run/"secret-that-must-not-be-read.json")
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertEqual(x["owner_private_subdirectories"],1)
        self.assertEqual(x["matched_run_dirs_with_manifest_metadata"],1)
        self.assertEqual(x["owner_private_manifest_metadata_files"],1)
        self.assertFalse(x["backup_content_read"])

    def test_05_unknown_subdirectory_not_interpreted_as_restore_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            run=root/"email_or_customer_backup"
            run.mkdir(mode=0o700)
            make_file(run/"manifest.json")
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertEqual(x["owner_private_subdirectories"],1)
        self.assertEqual(x["matched_run_dirs_with_manifest_metadata"],0)

    def test_06_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            (root/"fake.tar.gz").symlink_to("/etc/passwd")
            (root/"mojprop-unsafe").symlink_to("/tmp")
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertTrue(x["scan_completed"])
        self.assertEqual(x["owner_private_regular_archives"],0)
        self.assertEqual(x["owner_private_subdirectories"],0)

    def test_07_group_writable_archive_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            item=root/"suspicious.sql.gz"
            make_file(item)
            os.chmod(item,0o660)
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertEqual(x["owner_private_regular_archives"],0)

    def test_08_world_writable_backup_root_denied(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            os.chmod(root,0o702)
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertFalse(x["scan_completed"])
        self.assertFalse(x["root_safe"])

    def test_09_hardlinked_manifest_denied(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            f=root/"manifest.json"
            make_file(f)
            os.link(f,root/"other.json")
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertEqual(x["owner_private_manifest_metadata_files"],0)

    def test_10_more_than_128_entries_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            for i in range(module.MAX_ENTRIES+1):
                make_file(root/f"e{i}.zip")
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertFalse(x["scan_completed"])
        self.assertEqual(x["owner_private_regular_archives"],0)

    def test_11_more_than_64_private_dirs_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            for i in range(module.MAX_CHILDREN+1):
                (root/f"directory{i:03}").mkdir(mode=0o700)
            x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertFalse(x["scan_completed"])
        self.assertEqual(x["owner_private_subdirectories"],0)

    def test_12_regular_archives_do_not_require_read_content(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            make_file(root/"canary.tgz")
            with patch.object(builtins,"open",side_effect=AssertionError("content read prohibited")):
                x=module.scan_fixed_backup_root(root,os.geteuid())
        self.assertTrue(x["scan_completed"])
        self.assertEqual(x["owner_private_regular_archives"],1)

    def test_13_wrong_owner_not_authorized_to_scan_backup_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root=safe_root(td)
            x=module.scan_fixed_backup_root(root,os.geteuid()+12345)
        self.assertFalse(x["root_safe"])
        self.assertFalse(x["scan_completed"])

    def test_14_wrong_system_identity_blocks_report(self):
        with patch.object(module.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="not-owner")):
            x=module.report()
        self.assertFalse(x["owner_identity_verified"])
        self.assertFalse(x["production_release_authorized"])
        self.assertFalse(x["database_restore_verified"])
        self.assertFalse(x["backup_downloaded_or_created"])

    def test_15_fixed_inventory_is_safely_bounded_and_no_customer_data(self):
        self.assertEqual(module.MAX_ENTRIES,128)
        self.assertEqual(module.MAX_CHILDREN,64)
        self.assertIn("mojplaywin-moj-prop-backups",str(module.BACKUP_ROOT))
        with patch.object(module.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="not-owner")):
            x=module.report()
        for name in ("customer_data_accessed","backup_downloaded_or_created",
                     "database_accessed","external_network_called",
                     "production_release_authorized","cost_incurred",
                     "provider_offhost_backup_proven"):
            self.assertIs(x[name],False)

if __name__=="__main__":
    unittest.main()
