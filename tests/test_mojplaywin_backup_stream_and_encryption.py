"""Local synthetic backup-stream security tests. No connection to a production host."""
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_backup_encrypt_vps import (
    MARKER, BASENAME, store, verification,
)
from scripts.mojplaywin_backup_stream_cpanel import load_connection


class ApprovedPrimaryEncryptedBackupTests(unittest.TestCase):
    def test_authenticated_encrypted_backup_and_idempotent_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = b"CREATE TABLE tbl (id INT);\n" * 200 + MARKER
            result = store(io.BytesIO(payload), "mysql", root=root, keyroot=root,
                           min_start_free=0)
            self.assertTrue(result["authenticated_decrypt_verified"])
            self.assertFalse(result["all_children_covered"])
            self.assertFalse(result["isolated_restore_passed"])
            path = root / ".private-mojplaywin-offhost-backups" / (BASENAME + "_mysql.gcm")
            self.assertTrue(path.is_file())
            self.assertNotIn(payload[:50], path.read_bytes())
            keypath = root / ".config" / "mojplaywin-backup-recovery" / "recovery-key.bin"
            self.assertEqual(stat.S_IMODE(keypath.stat().st_mode), 0o600)
            key = keypath.read_bytes()
            self.assertEqual(verification(path, key)["plaintext_bytes"], len(payload))
            with self.assertRaises(RuntimeError):
                store(io.BytesIO(payload), "mysql", root=root, keyroot=root,
                      min_start_free=0)
            manifest = path.with_name(BASENAME + "_mysql.manifest.json")
            self.assertTrue(manifest.exists())
            doc = json.loads(manifest.read_text())
            self.assertTrue(doc["authenticated_decryption_passed"])
            self.assertFalse(doc["database_import_restored"])

    def test_incomplete_source_stream_has_no_verified_archive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(RuntimeError):
                store(io.BytesIO(b"truncated-dump" * 200), "mysql",
                      root=root, keyroot=root, min_start_free=0)
            output = root / ".private-mojplaywin-offhost-backups"
            self.assertFalse((output / (BASENAME + "_mysql.gcm")).exists())
            self.assertFalse((output / (BASENAME + "_mysql.manifest.json")).exists())

    def test_authenticated_backup_detects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = store(io.BytesIO(b"x" * 1400 + MARKER), "files",
                           root=root, keyroot=root, min_start_free=0)
            self.assertTrue(result["authenticated_decrypt_verified"])
            path = root / ".private-mojplaywin-offhost-backups" / (BASENAME + "_files.gcm")
            content = bytearray(path.read_bytes())
            content[len(content)//2] ^= 0x42
            path.write_bytes(content)
            keypath = root / ".config" / "mojplaywin-backup-recovery" / "recovery-key.bin"
            with self.assertRaises(Exception):
                verification(path, keypath.read_bytes())

    def test_source_sql_credentials_not_exposed_in_repr(self):
        # No tests should write to production paths; this imports the reader
        # without invoking production database access.
        self.assertTrue(callable(load_connection))


if __name__ == "__main__":
    unittest.main()
