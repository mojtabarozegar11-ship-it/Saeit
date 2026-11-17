"""C152 source-only integrity: synthetic backup fixtures, no production backup access."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c152_legacy_source_backup_sha256_readonly as mod


def fixture(root, run="4400000100", body=b"verified-synthetic-source"):
    folder=root/run
    folder.mkdir(mode=0o700)
    source=folder/"core/mojprop_views.py"
    source.parent.mkdir(mode=0o700)
    source.write_bytes(body)
    os.chmod(source,0o600)
    manifest={
        "run_id":run,"commit":"a"*40,
        "files":["config/settings.py","core/mojprop_views.py"],
        "config/settings.py":{"existed":True,"sha256":"b"*64,"mode":0o600},
        "core/mojprop_views.py":{"existed":True,
                                  "sha256":hashlib.sha256(body).hexdigest(),
                                  "mode":0o600},
    }
    (folder/"manifest.json").write_text(json.dumps(manifest))
    os.chmod(folder/"manifest.json",0o600)
    return folder,source,manifest


class LegacySourceHashTrustTests(unittest.TestCase):
    def test_01_legacy_manifest_only_allowlists_reviewed_code(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            pairs=mod.validate_legacy_manifest(m,folder.name)
        self.assertEqual(len(pairs[0]),1)
        self.assertEqual(pairs[0][0][0],"core/mojprop_views.py")
        self.assertEqual(pairs[1],1)

    def test_02_sha256_copy_matches_without_returning_content(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            result=mod._safe_source_file_sha(folder,"core/mojprop_views.py",os.geteuid())
        self.assertEqual(result[0],m["core/mojprop_views.py"]["sha256"])
        self.assertEqual(result[1],len(b"verified-synthetic-source"))

    def test_03_sensitive_settings_is_never_read(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            self.assertIsNone(mod._safe_source_file_sha(folder,"config/settings.py",
                                                         os.geteuid()))
        self.assertNotIn("config/settings.py",mod.ALLOWED_SOURCE)
        self.assertIn("config/settings.py",mod.SENSITIVE_EXCLUDE)

    def test_04_realistic_bounded_case_counts_valid_source_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            fixture(root)
            x=mod.inventory(root,os.geteuid())
        self.assertTrue(x["completed"])
        self.assertEqual(x["legacy_manifest_cases_recognized"],1)
        self.assertEqual(x["legacy_cases_with_all_allowed_source_hashes_matching"],1)
        self.assertEqual(x["allowed_source_copies_with_matching_sha256"],1)
        self.assertEqual(x["sensitive_or_unreviewed_source_entries_not_opened"],1)
        self.assertFalse(x["independent_db_app_media_restore_proven"])

    def test_05_corrupt_copy_sha_mismatch_does_not_confirm_case(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            source.write_bytes(b"tampered-private-source")
            x=mod.inventory(root,os.geteuid())
        self.assertEqual(x["allowed_source_copies_missing_or_mismatched"],1)
        self.assertEqual(x["legacy_cases_with_all_allowed_source_hashes_matching"],0)

    def test_06_source_symlink_does_not_read_outside_case(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            source.unlink()
            source.symlink_to("/etc/passwd")
            self.assertIsNone(mod._safe_source_file_sha(folder,"core/mojprop_views.py",
                                                         os.geteuid()))

    def test_07_group_writable_parent_disqualifies_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            os.chmod(source.parent,0o770)
            self.assertIsNone(mod._safe_source_file_sha(folder,"core/mojprop_views.py",
                                                         os.geteuid()))

    def test_08_overlarge_saved_source_denied(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root,body=b"x"*(mod.MAX_SOURCE_BYTES+1))
            self.assertIsNone(mod._safe_source_file_sha(folder,"core/mojprop_views.py",
                                                         os.geteuid()))

    def test_09_new_migration_flag_not_accepted_as_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            m["schema_migration_attempted"]=False
            self.assertIsNone(mod.validate_legacy_manifest(m,folder.name))

    def test_10_unknown_manifest_path_does_not_trigger_arbitrary_reads(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            m["files"]=["../.env"]
            m["../.env"]={"existed":True,"sha256":"a"*64,"mode":0o600}
            self.assertIsNone(mod.validate_legacy_manifest(m,folder.name))
            self.assertIsNone(mod._safe_source_file_sha(folder,"../.env",os.geteuid()))

    def test_11_missing_manifest_or_bad_owner_never_proves_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            folder,source,m=fixture(root)
            (folder/"manifest.json").unlink()
            self.assertIsNone(mod._read_small_fixed_json(folder/"manifest.json",
                                                          os.geteuid()))
            self.assertIsNone(mod._safe_source_file_sha(folder,"core/mojprop_views.py",
                                                         os.geteuid()+1))

    def test_12_more_than_128_entries_is_incomplete_not_no_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            for n in range(mod.MAX_ENTRIES+1):
                (root/f"unrelated{n}").mkdir()
            z=mod.inventory(root,os.geteuid())
        self.assertFalse(z["completed"])
        self.assertEqual(z["legacy_cases_with_all_allowed_source_hashes_matching"],0)

    def test_13_wrong_owner_blocks_fixed_cpanel_inventory(self):
        with patch.object(mod.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="wrong-owner")):
            z=mod.report()
        self.assertFalse(z["owner_identity_verified"])
        self.assertFalse(z["full_app_db_media_restore_proven"])
        self.assertFalse(z["production_deployment_authorized"])

    def test_14_source_bytes_never_returned_or_logged(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            fixture(root)
            z=mod.inventory(root,os.geteuid())
        self.assertNotIn("verified-synthetic-source",json.dumps(z))
        self.assertFalse(z["saved_source_contents_disclosed"])
        self.assertFalse(z["database_or_media_backup_read"])
        self.assertFalse(z["customer_data_accessed"])

    def test_15_schema_and_maximum_reads_restrict_restoration_claim(self):
        self.assertLessEqual(mod.MAX_ALL_READ_BYTES,64*1024*1024)
        self.assertLessEqual(mod.MAX_SOURCE_BYTES,512*1024)
        self.assertNotIn("config/settings.py",mod.ALLOWED_SOURCE)
        with patch.object(mod.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-owner")):
            result=mod.report()
        self.assertFalse(result["production_deployment_authorized"])
        self.assertFalse(result["offhost_independent_backup_proven"])
        self.assertFalse(result["full_app_db_media_restore_proven"])

if __name__=="__main__":
    unittest.main()
