"""Offline regression tests for owner two-Drive metadata-only preflight."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mojprop_owner_two_drive_quota_readonly_20261118 as m


class ReadOnlyCloudCapacityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "rclone.conf"
        self.exe = sys.executable

    def prepare_private_config(self):
        self.path.write_text('[factory_a]\ntype=drive\ntoken=DO_NOT_LOG_A\n'
                             '[factory_b]\ntype=drive\ntoken=DO_NOT_LOG_B\n')
        self.path.chmod(0o600)

    def test_01_no_config_denies_provider_access(self):
        with patch.object(m, "RcloneDualStore",
                          side_effect=AssertionError("NO_API_CALL")):
            data = m.readiness(config=self.path, rclone_exe=self.exe)
        self.assertEqual(data["status"], "MISSING_OWNER_AUTH")
        self.assertFalse(data["provider_quota_observed"])
        self.assertFalse(data["config_present_private"])

    def test_02_world_readable_config_denied(self):
        self.prepare_private_config()
        self.path.chmod(0o644)
        with patch.object(m, "RcloneDualStore",
                          side_effect=AssertionError("NO_API_CALL")):
            data = m.readiness(config=self.path, rclone_exe=self.exe)
        self.assertEqual(data["status"], "MISSING_OWNER_AUTH")
        self.assertFalse(data["config_present_private"])

    def test_03_symlinked_config_denied(self):
        self.prepare_private_config()
        target = self.path.with_suffix(".real")
        self.path.rename(target)
        self.path.symlink_to(target)
        with patch.object(m, "RcloneDualStore",
                          side_effect=AssertionError("NO_API_CALL")):
            data = m.readiness(config=self.path, rclone_exe=self.exe)
        self.assertFalse(data["config_present_private"])

    def test_04_no_pinned_rclone_does_not_read_oauth(self):
        self.prepare_private_config()
        with patch.object(m, "RcloneDualStore",
                          side_effect=AssertionError("NO_API_CALL")):
            data = m.readiness(config=self.path,
                               rclone_exe="/not/a/real/rclone")
        self.assertEqual(data["status"], "NO_PINNED_RCLONE_BINARY")
        self.assertTrue(data["config_present_private"])
        self.assertFalse(data["provider_quota_observed"])

    def test_05_success_is_only_diagnostic_not_real_backup_admission(self):
        self.prepare_private_config()
        record = SimpleNamespace(
            proof_readbacks_verified=True, distinct_private_roots=True,
            free_a_before=17_000_000_000, free_b_before=22_000_000_000,
        )
        with patch.object(m, "RcloneDualStore") as fake:
            fake.return_value.preflight.return_value = record
            data = m.readiness(config=self.path, rclone_exe=self.exe)
            args = fake.call_args.kwargs
        self.assertEqual(data["status"], "READONLY_PROVIDER_DIAGNOSTIC_OK")
        self.assertTrue(data["provider_quota_observed"])
        self.assertTrue(data["distinct_oauth_and_private_owner_proofs"])
        self.assertTrue(data["diagnostic_1mib_source_bound_admitted"])
        self.assertFalse(data["full_current_backup_capacity_admitted"])
        self.assertFalse(data["current_db_media_backup_created"])
        self.assertFalse(data["independent_restore_performed"])
        self.assertEqual(args["max_source_bytes"], 1024 * 1024)
        self.assertEqual(args["remote_a"], "factory_a")
        self.assertEqual(args["remote_b"], "factory_b")
        self.assertNotEqual(args["expected_root_a"], args["expected_root_b"])
        self.assertNotIn("DO_NOT_LOG", json.dumps(data))
        self.assertNotIn("17000000000", json.dumps(data))

    def test_06_provider_error_yields_fixed_private_redacted_code(self):
        self.prepare_private_config()
        with patch.object(m, "RcloneDualStore") as fake:
            fake.return_value.preflight.side_effect = m.TransferHold(
                "RCLONE_PROVIDER_OPERATION_FAILED")
            data = m.readiness(config=self.path, rclone_exe=self.exe)
        self.assertEqual(data["status"], "RCLONE_PROVIDER_OPERATION_FAILED")
        self.assertFalse(data["provider_quota_observed"])

    def test_07_unrecognized_error_must_not_leak_secret(self):
        self.prepare_private_config()
        with patch.object(m, "RcloneDualStore") as fake:
            fake.return_value.preflight.side_effect = m.TransferHold(
                "PRIVATE_REFRESH_TOKEN=DO_NOT_LOG_A")
            data = m.readiness(config=self.path, rclone_exe=self.exe)
        self.assertEqual(data["status"], "READONLY_PROVIDER_PROBE_FAILED")
        self.assertNotIn("DO_NOT_LOG", json.dumps(data))

    def test_08_runtime_exception_must_not_echo_provider_traceback(self):
        self.prepare_private_config()
        with patch.object(m, "RcloneDualStore") as fake:
            fake.return_value.preflight.side_effect = RuntimeError(
                "access_token=DO_NOT_LOG_B")
            data = m.readiness(config=self.path, rclone_exe=self.exe)
        self.assertEqual(data["status"], "UNEXPECTED_METADATA_PROBE_FAILURE")
        self.assertNotIn("DO_NOT_LOG", json.dumps(data))

    def test_09_trusted_roots_and_private_proof_are_exact(self):
        self.assertEqual(m._ROOT_A, "191sAkv4A01S9o6zhx-vM5xM7WO31qHPn")
        self.assertEqual(m._ROOT_B, "1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_")
        self.assertEqual(len(m._PROOF_SHA256), 64)
        self.assertEqual(m._DIAGNOSTIC_SOURCE_BYTES, 1 * 1024 * 1024)
        self.assertFalse(m.readiness(
            config=Path("/nonexistent-owner-rclone-config"),
            rclone_exe=self.exe)["cloud_objects_written_or_deleted"])


if __name__ == "__main__":
    unittest.main()
