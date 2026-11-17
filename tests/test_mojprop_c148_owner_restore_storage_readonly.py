"""C148 adversarial no-network tests for owner storage and restore metadata."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c148_owner_restore_storage_readonly as mod


class OwnerDiskRestoreTruthTests(unittest.TestCase):
    def test_01_existing_private_file_and_directory_are_safe(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root, 0o700)
            item=root/"lead_models.py"
            item.write_text("placeholder metadata test only", encoding="utf-8")
            os.chmod(item, 0o600)
            self.assertEqual(mod.classify_path(root, os.geteuid(), file=False), "safe")
            self.assertEqual(mod.classify_path(item, os.geteuid(), file=True), "safe")

    def test_02_group_writable_dir_is_diagnostic_not_restored(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root, 0o770)
            self.assertEqual(mod.classify_path(root, os.geteuid(), file=False),
                             "group_writable")

    def test_03_world_writable_dir_is_never_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root, 0o707)
            self.assertEqual(mod.classify_path(root, os.geteuid(), file=False),
                             "world_writable")

    def test_04_missing_file_is_distinct_from_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.assertEqual(mod.classify_path(root/"missing",os.geteuid(),file=True),
                             "missing")
            link=root/"link"
            link.symlink_to("/etc/passwd")
            self.assertEqual(mod.classify_path(link,os.geteuid(),file=True),
                             "symlink")

    def test_05_multiple_hardlinks_are_not_plain_safe_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            file=root/"file"
            file.write_text("dummy")
            os.link(file, root/"other")
            self.assertEqual(mod.classify_path(file,os.geteuid(),file=True),
                             "hardlinked")

    def test_06_directory_cannot_count_as_regular_model_file(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(mod.classify_path(Path(td),os.geteuid(),file=True),
                             "not_regular_file")

    def test_07_only_exact_bounded_private_restore_case_names_count(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root,0o700)
            for name in ("mojprop_restore_case0001","mojprop_restore_case0002",
                         "random", "mojprop_restore_badsym01"):
                (root/name).mkdir(mode=0o700)
            (root/"mojprop_restore_badsym01").chmod(0o770)
            (root/"mojprop_restore_badlink1").symlink_to("/tmp")
            data=mod.count_private_restore_cases(root,os.geteuid())
            self.assertTrue(data["bounded_scan_completed"])
            self.assertEqual(data["matching_owner_private_case_dirs"],2)
            self.assertFalse(data["read_any_receipt_or_backup"])
            self.assertFalse(data["independent_restore_proven"])

    def test_08_unbounded_archive_case_scan_returns_undetermined(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root,0o700)
            for i in range(mod.MAX_ENTRIES+1):
                (root/f"item{i}").mkdir()
            data=mod.count_private_restore_cases(root,os.geteuid())
            self.assertFalse(data["bounded_scan_completed"])
            self.assertEqual(data["matching_owner_private_case_dirs"],0)
            self.assertFalse(data["independent_restore_proven"])

    def test_09_nonprivate_root_does_not_get_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root,0o770)
            data=mod.count_private_restore_cases(root,os.geteuid())
            self.assertFalse(data["bounded_scan_completed"])

    def test_10_real_statvfs_does_not_claim_independent_quota(self):
        with tempfile.TemporaryDirectory() as td:
            data=mod.normalized_disk_usage(Path(td))
            self.assertTrue(data["measured"])
            self.assertGreater(data["total_mib_floor"],0)
            self.assertGreaterEqual(data["available_mib_floor"],0)
            self.assertFalse(data["account_quota_free_bytes_verified"])
            self.assertFalse(data["independent_offhost_restore_space_verified"])

    def test_11_statvfs_missing_or_unavailable_is_not_zero_capacity_claim(self):
        data=mod.normalized_disk_usage(Path("/not-a-mounted-path-for-this-test"))
        self.assertFalse(data["measured"])
        self.assertIsNone(data["available_mib_floor"])

    def test_12_wrong_user_is_not_owner_confirmed_or_safe(self):
        with patch.object(mod.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-zomorod2")):
            data=mod.report()
        self.assertFalse(data["owner_identity_verified"])
        self.assertFalse(data["full_app_db_media_restore_verified"])
        self.assertFalse(data["production_deployment_authorized"])
        self.assertFalse(data["backup_content_read"])

    def test_13_no_database_payment_backup_content_or_deploy_functions(self):
        script=Path(mod.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "subprocess.", "urllib.", "requests.", "shutil.copy",
            "tarfile.open", "open(", "read_bytes(", "read_text(",
            "cursor(", "migrate(", "chmod(", "chown(", "remove(",
        ):
            # Literals in comments are not executable functionality; the
            # scanner does not call these APIs.
            self.assertNotIn(forbidden, script)
        self.assertEqual(mod.MAX_ENTRIES,128)

    def test_14_no_privacy_or_release_proof_claims(self):
        with patch.object(mod.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="foreign")):
            data=mod.report()
        for field in ("account_quota_verified","offhost_backup_verified",
                      "full_app_db_media_restore_verified","customer_data_accessed",
                      "database_accessed","external_network_called",
                      "payment_created","production_deployment_authorized",
                      "cost_incurred"):
            self.assertIs(data[field],False)
        self.assertEqual(set(data["fixed_path_states"]),{
            "home","staging","webroot","prop_firm_dir",
            "prop_interest_model_file","local_plan1_backup_dir",
            "independent_restore_evidence_dir",
        })

if __name__=="__main__":
    unittest.main()
