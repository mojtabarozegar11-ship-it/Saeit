"""Synthetic regression tests for Zomorod encrypted offsite artifact recovery.

Never reads production data, GitHub credentials, or real private keys.
"""
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from f01_encrypted_stream_v1 import encrypt


class OfflineRestoreDrillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Synthetic disposable RSA key only; never confuse it with the owner's key.
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        cls.passphrase = b"synthetic-unrelated-test-passphrase"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir(mode=0o700)
        self.private = self.root / "synthetic-private.pem"
        self.public = self.root / "synthetic-public.pem"
        self.passfile = self.root / "password.txt"
        self.private.write_bytes(self.key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(self.passphrase),
        ))
        self.public.write_bytes(self.key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.passfile.write_bytes(self.passphrase)
        self.private.chmod(0o600)
        self.passfile.chmod(0o600)
        self.db = self.root / "synthetic.sqlite3"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
            conn.execute("CREATE TABLE journal_entries (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE journal_lines (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE invoices (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO users (email) VALUES ('test@example.invalid')")
        self.cipher = self.root / "synthetic.f01enc"
        encrypt(self.db, self.cipher, self.public)
        self.expected = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.archive = self.root / "artifact.zip"
        self.make_archive()

    def make_archive(self, *, manifest=None, ciphertext=None, extra=None):
        if manifest is None:
            manifest = ("format=F01ENC-RSA3072-AES256GCM-V1\n"
                        "snapshot_sha256=" + self.expected + "\n")
        if ciphertext is None:
            ciphertext = self.cipher.read_bytes()
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as out:
            out.writestr("manifest.txt", manifest)
            out.writestr("business.sqlite3.f01enc", ciphertext)
            if extra is not None:
                out.writestr(extra, b"not expected")

    def invoke(self, *, key=None, expected=None):
        cmd = [
            sys.executable, str(ROOT / "scripts/zm_offsite_restore_drill.py"),
            "--artifact-zip", str(self.archive),
            "--private-key", str(key or self.private),
            "--passphrase-file", str(self.passfile),
            "--scratch-root", str(self.scratch),
        ]
        if expected is not None:
            cmd.extend(["--expected-snapshot-sha256", expected])
        result = subprocess.run(cmd, text=True, capture_output=True)
        self.assertEqual(list(self.scratch.iterdir()), [], "Offline plaintext survived")
        return result

    def test_valid_encrypted_zip_decrypts_and_checks_sqlite_then_erases(self):
        result = self.invoke(expected=self.expected)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OFFSITE_RESTORE_VERIFIED=true", result.stdout)
        self.assertIn("OFFSITE_PLAINTEXT_RETAINED=false", result.stdout)
        self.assertIn("OFFSITE_SQLITE_INTEGRITY=ok", result.stdout)

    def test_tampered_gcm_ciphertext_rejected(self):
        data = bytearray(self.cipher.read_bytes())
        data[-1] ^= 1
        self.make_archive(ciphertext=bytes(data))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OFFSITE_RESTORE_VERIFIED=false", result.stderr)

    def test_wrong_snapshot_digest_rejected(self):
        self.make_archive(manifest="format=F01ENC-RSA3072-AES256GCM-V1\n"
                                   + "snapshot_sha256=" + "0" * 64 + "\n")
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_untrusted_archive_entries_rejected(self):
        self.make_archive(extra="../unexpected")
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse((self.root / "unexpected").exists())

    def test_required_key_is_never_optional(self):
        self.assertNotEqual(self.invoke(key=self.root / "not-a-key").returncode, 0)

    def test_wrong_external_expected_digest_rejected(self):
        self.assertNotEqual(self.invoke(expected="f" * 64).returncode, 0)

    def test_unauthenticated_corrupt_sqlite_rejected_after_decrypt(self):
        self.db.write_bytes(b"This is not SQLite content")
        self.cipher.unlink()
        encrypt(self.db, self.cipher, self.public)
        self.expected = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.make_archive()
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_world_readable_private_key_rejected(self):
        self.private.chmod(0o644)
        self.assertNotEqual(self.invoke().returncode, 0)


if __name__ == "__main__":
    unittest.main()
