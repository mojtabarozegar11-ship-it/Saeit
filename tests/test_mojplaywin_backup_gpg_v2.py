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

    def test_unique_timestamped_archive_name(self):
        from scripts.mojplaywin_backup_encrypt_vps_gpg import STEM
        self.assertRegex(STEM, r"^mojplaywin_\d{8}T\d{6}Z_[0-9a-f]{16}$")

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
            self.assertFalse((f/(STEM+"_files_"+VERSION+".gpg.partial")).exists())

    def test_sql_raw_ceiling_failure_removes_only_new_partial(self):
        from unittest.mock import patch
        from scripts import mojplaywin_backup_encrypt_vps_gpg as sink
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            with patch.object(sink, "MAX_MYSQL_SOURCE_BYTES", 64):
                with self.assertRaisesRegex(RuntimeError, "source exceeds safety maximum"):
                    sink.store(io.BytesIO(b"synthetic" * 200 + sink.MARKER), "mysql",
                               root=base, keyroot=base, minimum_free=0)
            folder=base/".private-mojplaywin-offhost-backups"
            self.assertFalse((folder/(sink.STEM+"_mysql_"+sink.VERSION+".gpg.partial")).exists())
            self.assertFalse((folder/(sink.STEM+"_mysql_"+sink.VERSION+".gpg")).exists())

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


class RawBackupLimitTests(unittest.TestCase):
    def test_mysql_only_ceiling_raised_without_relaxing_disk_or_file_limits(self):
        from scripts import mojplaywin_backup_stream_cpanel as source
        from scripts import mojplaywin_backup_encrypt_vps_gpg as destination
        from scripts import mojplaywin_recovery_stream_vps as recovery
        gib = 1024**3
        self.assertEqual(source.MAX_STREAM, 12 * gib)
        self.assertEqual(source.MAX_MYSQL_STREAM, 48 * gib)
        self.assertEqual(destination.MAX_SOURCE_BYTES, 12 * gib)
        self.assertEqual(destination.MAX_MYSQL_SOURCE_BYTES, 48 * gib)
        self.assertEqual(recovery.MAX_PLAINTEXT_BYTES, 48 * gib)
        self.assertEqual(source.MAX_MYSQL_STREAM, destination.MAX_MYSQL_SOURCE_BYTES)
        self.assertEqual(source.MAX_MYSQL_STREAM, recovery.MAX_PLAINTEXT_BYTES)
        self.assertEqual(destination.MAX_ENCRYPTED_BYTES, 12 * gib)
        self.assertEqual(destination.MIN_START_FREE, 10 * gib)

    def test_source_stream_respects_explicit_cap_without_allocating_gib(self):
        from unittest.mock import patch
        from scripts import mojplaywin_backup_stream_cpanel as source
        class SyntheticProcess:
            stdout = io.BytesIO(b"123456789")
            killed = False
            def wait(self, timeout=None):
                return 0
            def poll(self):
                return None if not self.killed else 0
            def kill(self):
                self.killed = True
        fake = SyntheticProcess()
        with patch.object(source.subprocess, "Popen", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "safety cap"):
                source.copy_exact_process_stdout(["synthetic-no-process"], max_stream=8)
        self.assertTrue(fake.killed)


if __name__ == "__main__":
    unittest.main()
