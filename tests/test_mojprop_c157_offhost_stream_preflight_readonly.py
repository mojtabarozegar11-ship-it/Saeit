"""No production data: C157 media/dump/encryption preflight regressions."""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c157_offhost_stream_preflight_readonly as m


class OffhostStreamReadinessTests(unittest.TestCase):
    def test_01_exact_fixed_known_tool_names_no_execution(self):
        self.assertEqual(set(m.TOOL_PATHS),
                         {"mariadb_dump","mysqldump","age","gpg","openssl","gzip"})
        self.assertEqual(m.MAX_ENTRIES,64)

    def test_02_known_media_roots_fixed_to_known_owner(self):
        self.assertEqual(len(m.MEDIA_CANDIDATES),5)
        self.assertTrue(all(str(p).startswith("/home/zomorod2/")
                            for p in m.MEDIA_CANDIDATES.values()))

    def test_03_safe_binary_requires_root_executable(self):
        with patch.object(m.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755,st_uid=0)), \
             patch.object(m.os,"access",return_value=True):
            self.assertTrue(m._safe_executable("/usr/bin/age"))

    def test_04_nonexec_program_unavailable(self):
        with patch.object(m.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o600,st_uid=0)), \
             patch.object(m.os,"access",return_value=False):
            self.assertFalse(m._safe_executable("/usr/bin/age"))

    def test_05_untrusted_symlink_target_denied(self):
        with patch.object(m.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFLNK | 0o777,st_uid=0)), \
             patch.object(m.os.path,"realpath",return_value="/tmp/untrusted"):
            self.assertFalse(m._safe_executable("/usr/bin/gpg"))

    def test_06_trusted_rootowned_symlink_allowed_metadata_only(self):
        with patch.object(m.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFLNK | 0o777,st_uid=0)), \
             patch.object(m.os.path,"realpath",return_value="/usr/bin/gpg.real"), \
             patch.object(m.os,"stat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755,st_uid=0)), \
             patch.object(m.os,"access",return_value=True):
            self.assertTrue(m._safe_executable("/usr/bin/gpg"))

    def test_07_group_writable_tool_denied(self):
        with patch.object(m.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o775,st_uid=0)), \
             patch.object(m.os,"access",return_value=True):
            self.assertFalse(m._safe_executable("/usr/bin/age"))

    def test_08_owner_private_media_dir_metadata_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            (root/"video.dat").write_bytes(b"test-only")
            (root/"subdir").mkdir(mode=0o700)
            result=m.media_metadata(root,os.geteuid())
        self.assertTrue(result["owner_dir_safe"])
        self.assertTrue(result["direct_scan_complete"])
        self.assertEqual(result["direct_regular_files"],1)
        self.assertEqual(result["direct_subdirectories"],1)
        self.assertEqual(result["direct_regular_bytes_upper_observed"],9)
        self.assertFalse(result["recursive_media_scope_proven"])
        self.assertFalse(result["media_content_read"])

    def test_09_symlink_in_media_dir_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            (root/"untrusted").symlink_to("/etc/passwd")
            out=m.media_metadata(root,os.geteuid())
        self.assertEqual(out["direct_regular_files"],0)
        self.assertEqual(out["direct_subdirectories"],0)

    def test_10_group_world_writable_media_root_denied(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o770)
            out=m.media_metadata(root,os.geteuid())
        self.assertFalse(out["owner_dir_safe"])
        self.assertFalse(out["direct_scan_complete"])

    def test_11_bounded_direct_scan_never_declares_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            for i in range(m.MAX_ENTRIES+1):
                (root/f"synthetic_{i}").mkdir(mode=0o700)
            out=m.media_metadata(root,os.geteuid())
        self.assertTrue(out["owner_dir_safe"])
        self.assertFalse(out["direct_scan_complete"])
        self.assertEqual(out["direct_regular_files"],0)

    def test_12_missing_media_root_unknown_not_empty(self):
        with tempfile.TemporaryDirectory() as td:
            out=m.media_metadata(Path(td)/"not-present",os.geteuid())
        self.assertFalse(out["owner_dir_safe"])
        self.assertFalse(out["direct_scan_complete"])

    def test_13_wrong_owner_blocks_all_live_checks(self):
        with patch.object(m.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="foreign")), \
             patch.object(m,"check_tools") as tools:
            out=m.report()
        tools.assert_not_called()
        self.assertFalse(out["owner_identity_verified"])
        self.assertFalse(out["db_dump_executed"])
        self.assertFalse(out["production_deployment_authorized"])

    def test_14_not_even_a_public_recipient_claim(self):
        with patch.object(m.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="foreign")):
            out=m.report()
        for key in ("recipient_public_key_verified",
                    "database_connection_and_consistent_snapshot_verified",
                    "actual_live_media_root_verified","account_quota_verified",
                    "offhost_db_media_restore_proven",
                    "db_dump_executed","encryption_executed",
                    "database_or_media_contents_read",
                    "offhost_source_artifact_revalidated_in_this_probe",
                    "production_deployment_authorized","cost_incurred"):
            self.assertIs(out[key],False)

    def test_15_no_shell_external_process_database_or_file_reads(self):
        source=Path(m.__file__).read_text(encoding="utf-8")
        for forbidden in ("subprocess.", "os.system(", "tarfile.",
                          "shutil.copy", "read_bytes(", "read_text(",
                          "mysql.connector", "psycopg", "cursor(",
                          "os.remove(", "os.unlink("):
            self.assertNotIn(forbidden,source)
        self.assertIn("entry.stat(follow_symlinks=False)",source)

if __name__=="__main__":
    unittest.main()
