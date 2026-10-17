"""Synthetic GPG-only tests. Never connects to private hosts or reads live data."""
import io
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

@unittest.skipUnless(shutil.which("gpg"), "GPG is required by dedicated backup workflow")
class GpgStreamingBackupTests(unittest.TestCase):
    def test_synthetic_gpg_algorithm_operational(self):
        from scripts.mojplaywin_backup_encrypt_vps_gpg import selftest
        self.assertTrue(selftest())

    def test_round_trip_and_existing_backup_no_overwrite(self):
        from scripts.mojplaywin_backup_encrypt_vps_gpg import (
            store, MARKER, STEM, VERSION
        )
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            payload=b"private test fixture no customer content" * 120 + MARKER
            result=store(io.BytesIO(payload), "mysql", root=base, keyroot=base, minimum_free=0)
            self.assertTrue(result["decryption_verified"])
            self.assertFalse(result["full_tenant_backup"])
            f=base/".private-mojplaywin-offhost-backups"/(STEM+"_mysql_"+VERSION+".gpg")
            self.assertTrue(f.is_file())
            self.assertNotIn(payload[:60],f.read_bytes())
            key=base/".config"/"mojplaywin-backup-recovery"/"recovery-key.bin"
            self.assertEqual(stat.S_IMODE(key.stat().st_mode),0o600)
            with self.assertRaises(RuntimeError):
                store(io.BytesIO(payload), "mysql", root=base, keyroot=base, minimum_free=0)

    def test_bad_source_missing_marker_never_marked_complete(self):
        from scripts.mojplaywin_backup_encrypt_vps_gpg import store, STEM, VERSION
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            with self.assertRaises(RuntimeError):
                store(io.BytesIO(b"bad source" * 200), "files",
                      root=base, keyroot=base, minimum_free=0)
            f=base/".private-mojplaywin-offhost-backups"
            self.assertFalse((f/(STEM+"_files_"+VERSION+".gpg")).exists())
            self.assertFalse((f/(STEM+"_files_"+VERSION+".manifest.json")).exists())

    def test_tampered_file_fails_openpgp_integrity(self):
        from scripts.mojplaywin_backup_encrypt_vps_gpg import (
            store, verify_stream, recovery_key, STEM, VERSION, MARKER
        )
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            store(io.BytesIO(b"fixture" * 500 + MARKER), "files",
                  root=base, keyroot=base, minimum_free=0)
            file=base/".private-mojplaywin-offhost-backups"/(STEM+"_files_"+VERSION+".gpg")
            data=bytearray(file.read_bytes())
            data[len(data)//2] ^= 1
            file.write_bytes(data)
            secret_dir=base/".config"/"mojplaywin-backup-recovery"
            with self.assertRaises(Exception):
                verify_stream(file,secret_dir/"gnupg-v2", recovery_key(secret_dir/"recovery-key.bin"))


if __name__ == "__main__":
    unittest.main()
