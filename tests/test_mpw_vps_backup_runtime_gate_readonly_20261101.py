"""Synthetic-only regression for the VPS read-only recovery-key metadata gate."""
import os
from pathlib import Path
import tempfile
import unittest

from scripts.mpw_vps_backup_runtime_gate_readonly_20261101 import inspect


class VpsRuntimePrerequisiteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.uid = os.geteuid()
        self.secret = self.base / ".config" / "mojplaywin-backup-recovery"
        self.secret.mkdir(parents=True)
        self.secret.chmod(0o700)
        self.key = self.secret / "recovery-key.bin"
        self.key.write_bytes(b"S" * 32)
        self.key.chmod(0o600)

    def probe(self, **kw):
        return inspect(self.base, uid=self.uid, gpg_available=True,
                       free_bytes=12 * 1024**3, **kw)

    def test_existing_private_key_and_space_ready_without_reading_it(self):
        report = self.probe()
        self.assertTrue(report["owner_armed_backup_runtime_prerequisites_ready"])
        self.assertFalse(report["recovery_key_bytes_read"])
        self.assertFalse(report["archive_created"])
        self.assertFalse(report["release_permitted"])
        self.assertNotIn("recovery-key.bin", str(report))
        self.assertNotIn(str(self.base), str(report))

    def test_wrong_key_size_or_permissions_fail_closed(self):
        self.key.write_bytes(b"S" * 31)
        self.assertFalse(self.probe()["owner_armed_backup_runtime_prerequisites_ready"])
        self.key.write_bytes(b"S" * 32)
        self.key.chmod(0o644)
        self.assertFalse(self.probe()["owner_armed_backup_runtime_prerequisites_ready"])

    def test_key_symlink_rejected(self):
        ordinary = self.base / "synthetic-key"
        ordinary.write_bytes(b"S" * 32)
        self.key.unlink()
        self.key.symlink_to(ordinary)
        self.assertFalse(self.probe()["owner_armed_backup_runtime_prerequisites_ready"])

    def test_low_capacity_rejected(self):
        report = inspect(self.base, uid=self.uid, gpg_available=True,
                         free_bytes=9 * 1024**3)
        self.assertFalse(report["free_capacity_meets_10gib_admission"])
        self.assertFalse(report["owner_armed_backup_runtime_prerequisites_ready"])

    def test_missing_key_rejected_and_no_key_created(self):
        self.key.unlink()
        report = self.probe()
        self.assertFalse(report["existing_recovery_key_metadata_owner_only_32_bytes"])
        self.assertFalse(self.key.exists())
        self.assertFalse(report["owner_armed_backup_runtime_prerequisites_ready"])


if __name__ == "__main__":
    unittest.main()
