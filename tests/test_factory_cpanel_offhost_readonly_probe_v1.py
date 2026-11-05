"""Offline and non-mutating cPanel vault suitability tests."""

from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from factory_cpanel_offhost_readonly_probe_v1 import (  # noqa: E402
    MIB, _read_cpanel_quota, inspect,
)


class CpanelOffhostProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.home.chmod(0o700)
        self.vault = self.home / ".saeit-factory-offhost"
        self.vault.mkdir(mode=0o700)
        self.quota = (20_000 * MIB, 30_000 * MIB)

    def probe(self, **extra):
        return inspect(
            self.home, uid=os.getuid(), quota_bytes=self.quota,
            disk_free_bytes=9_000 * MIB, **extra,
        )

    def test_full_room_and_private_candidate_still_hold_transfer(self):
        result = self.probe()
        self.assertTrue(result["vault_candidate_private"])
        self.assertTrue(result["capacity_candidate_pass"])
        self.assertEqual(result["status"], "HOLD_NO_TRANSFER_AUTHORIZED")
        self.assertFalse(result["transfer_authorized"])
        self.assertFalse(result["independent_restore_verified"])

    def test_missing_vault_fails_closed_without_creation(self):
        self.vault.rmdir()
        result = self.probe()
        self.assertEqual(result["vault"], "CPANEL_VAULT_MISSING")
        self.assertFalse(self.vault.exists())

    def test_symlink_vault_is_rejected(self):
        self.vault.rmdir()
        self.vault.symlink_to(self.home)
        self.assertEqual(self.probe()["vault"], "CPANEL_VAULT_SYMLINK_PATH")

    def test_insecure_mode_rejected(self):
        self.vault.chmod(0o755)
        self.assertEqual(self.probe()["vault"], "CPANEL_VAULT_PERMISSIONS_UNSAFE")

    def test_insufficient_quota_rejected_even_with_host_disk_free(self):
        result = inspect(
            self.home, uid=os.getuid(), quota_bytes=(29_000 * MIB, 30_000 * MIB),
            disk_free_bytes=50_000 * MIB,
        )
        self.assertFalse(result["capacity_candidate_pass"])

    def test_insufficient_filesystem_rejected_even_with_quota(self):
        result = inspect(
            self.home, uid=os.getuid(), quota_bytes=self.quota,
            disk_free_bytes=100 * MIB,
        )
        self.assertFalse(result["capacity_candidate_pass"])

    def test_unknown_quota_not_treated_as_unlimited(self):
        with patch("factory_cpanel_offhost_readonly_probe_v1._read_cpanel_quota", side_effect=ValueError):
            result = inspect(self.home, uid=os.getuid(), disk_free_bytes=50_000 * MIB)
        self.assertIsNone(result["quota_headroom_bytes"])
        self.assertFalse(result["capacity_candidate_pass"])

    def test_uapi_response_is_minimized_to_numeric_quota(self):
        mock = type("Command", (), {"returncode": 0, "stdout": '{"result":{"data":{"megabytes_used":"27407.96","megabyte_limit":30720,"sensitive":"not-exported"}}}'})
        with patch("factory_cpanel_offhost_readonly_probe_v1.subprocess.run", return_value=mock):
            used, limit = _read_cpanel_quota()
        self.assertEqual(used, int(27407.96 * MIB))
        self.assertEqual(limit, 30720 * MIB)

    def test_unlimited_or_malformed_quota_is_rejected(self):
        mock = type("Command", (), {"returncode": 0, "stdout": '{"result":{"data":{"megabytes_used":10,"megabyte_limit":"unlimited"}}}'})
        with patch("factory_cpanel_offhost_readonly_probe_v1.subprocess.run", return_value=mock):
            with self.assertRaises(ValueError):
                _read_cpanel_quota()

    def test_argument_limits_protect_resource_estimate(self):
        with self.assertRaisesRegex(ValueError, "CPANEL_UNSAFE_CAPACITY_ARGUMENT"):
            self.probe(checkpoint_cap_mib=99999)


if __name__ == "__main__":
    unittest.main()
