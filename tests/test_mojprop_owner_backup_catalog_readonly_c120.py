"""C120 zero-write cPanel Backup UAPI catalog privacy/fail-closed regressions."""
import json
import stat
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.mojprop_owner_backup_catalog_readonly_c120 import (
    MAX_API_BYTES, classify_backup_catalog, inspect,
)


def response(data, status=1):
    return {"result": {"status": status, "data": data}}


class OwnerBackupCatalogOnlyC120Tests(unittest.TestCase):
    def test_01_valid_local_backup_metadata_not_restoration_proof(self):
        out = classify_backup_catalog(response([
            {"file": "backup-account.tar.gz", "status": "complete"},
            {"file": "backup-in-progress.tar.gz", "status": "pending"},
        ]))
        self.assertTrue(out["catalog_schema_recognized"])
        self.assertEqual(out["backup_entries_reported"], 2)
        self.assertEqual(out["completed_archive_metadata_entries"], 1)
        self.assertTrue(out["possible_local_account_archive_present"])
        self.assertNotIn("backup-account", str(out))

    def test_02_no_backups_returns_exact_empty_not_signed_restorable(self):
        out = classify_backup_catalog(response([]))
        self.assertTrue(out["catalog_schema_recognized"])
        self.assertEqual(out["backup_entries_reported"], 0)
        self.assertFalse(out["possible_local_account_archive_present"])

    def test_03_api_status_bool_must_not_count_as_numeric_success(self):
        out = classify_backup_catalog(response([], True))
        self.assertFalse(out["catalog_schema_recognized"])

    def test_04_unknown_provider_payload_never_invents_backups(self):
        for payload in (None, [], {}, {"result": {"status": 1, "data": None}},
                        {"result": {"status": 1, "data": {}}},
                        response([{"file": "a"}] * 101)):
            with self.subTest(payload=str(type(payload))):
                self.assertFalse(classify_backup_catalog(payload)["catalog_schema_recognized"])

    def test_05_pending_or_unknown_status_does_not_count_as_completed(self):
        out = classify_backup_catalog(response([
            {"file": "x", "status": "pending"},
            {"file": "y", "status": "broken"},
            {"file": "z", "status": True},
        ]))
        self.assertEqual(out["completed_archive_metadata_entries"], 0)

    def test_06_invalid_file_field_does_not_leak(self):
        out = classify_backup_catalog(response([
            {"file": ["buyer@example.com"], "status": "complete"},
            {"file": "", "status": "complete"},
            {"file": "x" * 300, "status": "complete"},
        ]))
        self.assertEqual(out["completed_archive_metadata_entries"], 0)
        self.assertNotIn("buyer@", str(out))

    def _run(self, *, stdout=None, owner="zomorod2", mode=None):
        from scripts import mojprop_owner_backup_catalog_readonly_c120 as mod
        payload = stdout if stdout is not None else json.dumps(
            response([{"file": "local.tar.gz", "status": "complete"}])
        ).encode()
        if mode is None:
            mode = stat.S_IFREG | 0o755
        with patch.object(mod.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name=owner)), \
             patch.object(mod.os, "geteuid", return_value=1000), \
             patch.object(mod.os, "lstat",
                          return_value=SimpleNamespace(st_mode=mode, st_uid=0)), \
             patch.object(mod.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout=payload)) as cmd:
            result = mod.inspect()
        return result, cmd

    def test_07_account_owner_required_before_any_uapi_call(self):
        result, cmd = self._run(owner="other-user")
        self.assertFalse(result["owner_identity_verified"])
        cmd.assert_not_called()

    def test_08_nonregular_or_group_writable_binary_denied(self):
        for mode in (stat.S_IFLNK | 0o777, stat.S_IFREG | 0o775,
                     stat.S_IFDIR | 0o755):
            with self.subTest(mode=mode):
                result, cmd = self._run(mode=mode)
                self.assertFalse(result["uapi_program_safe"])
                cmd.assert_not_called()

    def test_09_only_exact_read_only_api_method_and_account_is_called(self):
        result, cmd = self._run()
        self.assertTrue(result["uapi_query_completed"])
        args, kwargs = cmd.call_args
        self.assertEqual(args[0], [
            "/usr/bin/uapi", "--output=json", "--user=zomorod2",
            "Backup", "list_backups",
        ])
        self.assertFalse(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])
        self.assertLessEqual(kwargs["timeout"], 14)
        self.assertNotIn("password", str(args).lower())

    def test_10_oversized_or_malformed_api_reply_stays_untrusted(self):
        for output in (b"not JSON", b"x" * (MAX_API_BYTES+1), b""):
            with self.subTest(length=len(output)):
                result, _ = self._run(stdout=output)
                self.assertFalse(result["catalog_schema_recognized"])

    def test_11_metadata_is_never_an_independent_restore_authorization(self):
        result, _ = self._run()
        self.assertEqual(result["backup_entries_reported"], 1)
        for flag in ("provider_offhost_backup_verified",
                     "independent_encrypted_full_restore_proven",
                     "production_release_authorized",
                     "database_accessed", "customer_records_accessed",
                     "backup_files_opened_or_downloaded", "cost_incurred"):
            self.assertIs(result[flag], False)

    def test_13_owner_cli_fallback_only_when_administrative_mode_denied(self):
        from scripts import mojprop_owner_backup_catalog_readonly_c120 as mod
        denied = SimpleNamespace(returncode=1, stdout=b"", stderr=b"secret")
        usable = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(response([])).encode(),
        )
        with patch.object(mod.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name="zomorod2")), \
             patch.object(mod.os, "geteuid", return_value=1000), \
             patch.object(mod.os, "lstat",
                          return_value=SimpleNamespace(
                              st_mode=stat.S_IFREG | 0o755, st_uid=0)), \
             patch.object(mod.subprocess, "run",
                          side_effect=[denied, usable]) as cmd:
            result = mod.inspect()
        self.assertEqual(cmd.call_count, 2)
        self.assertEqual(cmd.call_args.args[0], [
            "/usr/bin/uapi", "--output=json", "Backup", "list_backups",
        ])
        self.assertTrue(result["catalog_schema_recognized"])
        self.assertEqual(result["uapi_outcome"], "catalog_recognized")
        self.assertEqual(result["backup_entries_reported"], 0)
        self.assertNotIn("secret", str(result))

    def test_14_two_failed_modes_report_unknown_not_zero_backups(self):
        from scripts import mojprop_owner_backup_catalog_readonly_c120 as mod
        failed = SimpleNamespace(returncode=1, stdout=b"", stderr=b"private-example-backup-archive-name")
        with patch.object(mod.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name="zomorod2")), \
             patch.object(mod.os, "geteuid", return_value=1000), \
             patch.object(mod.os, "lstat",
                          return_value=SimpleNamespace(
                              st_mode=stat.S_IFREG | 0o755, st_uid=0)), \
             patch.object(mod.subprocess, "run",
                          return_value=failed) as cmd:
            result = mod.inspect()
        self.assertEqual(cmd.call_count, 2)
        self.assertFalse(result["uapi_query_completed"])
        self.assertFalse(result["catalog_schema_recognized"])
        self.assertEqual(result["uapi_outcome"],
                         "cli_nonzero_or_feature_unavailable")
        self.assertNotIn("private-example-backup-archive-name", str(result))
        self.assertFalse(result["production_release_authorized"])

    def test_12_local_archive_path_data_is_never_exposed_in_report(self):
        data = response([{
            "file": "/home/zomorod2/private_db_customer@example.org.sql.gz",
            "status": "complete", "token": "secret",
        }])
        result, _ = self._run(stdout=json.dumps(data).encode())
        self.assertEqual(result["completed_archive_metadata_entries"], 1)
        self.assertNotIn("secret", str(result))
        self.assertNotIn("customer@", str(result))
