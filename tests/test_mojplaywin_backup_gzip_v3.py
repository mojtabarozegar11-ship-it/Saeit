"""Fixture-only recovery and transport tests for the opt-in gzip-before-SSH path."""
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from scripts import mojplaywin_backup_gzip_source_v3 as src
from scripts import mojplaywin_backup_encrypt_vps_gpg as enc
from scripts import mojplaywin_backup_gzip_recovery_v3 as recovery


class FastSourceTests(unittest.TestCase):
    def test_producer_is_true_gzip_member_then_footer(self):
        self.assertEqual(src.MARKER, enc.MARKER)
        binary = io.BytesIO()
        command = [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'A'*250000)"]
        meta = src.compress_process(command, out=binary)
        value = binary.getvalue()
        self.assertTrue(value.endswith(enc.MARKER))
        self.assertEqual(zlib.decompress(value[:-len(enc.MARKER)], wbits=31), b"A" * 250000)
        self.assertLess(meta["gzip_bytes"], meta["raw_bytes"])

    def test_failed_source_cannot_emit_completion_marker(self):
        binary = io.BytesIO()
        command = [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'x'*2048);sys.exit(3)"]
        with self.assertRaises(RuntimeError):
            src.compress_process(command, out=binary)
        self.assertFalse(binary.getvalue().endswith(enc.MARKER))

    def test_source_size_limit_prevents_success_receipt(self):
        binary = io.BytesIO()
        command = [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'x'*5000)"]
        with self.assertRaises(RuntimeError):
            src.compress_process(command, out=binary, max_raw=1000)
        self.assertFalse(binary.getvalue().endswith(enc.MARKER))


@unittest.skipUnless(shutil.which("gpg"), "GPG needed for crypto fixture tests")
class FastGpgTests(unittest.TestCase):
    def setUp(self):
        ctx = tempfile.TemporaryDirectory()
        self.addCleanup(ctx.cleanup)
        self.base = Path(ctx.name)
        self.payload = b"random synthetic internal test record\n" * 30000
        self.compressed = zlib.compressobj(1, zlib.DEFLATED, 31)
        self.source = self.compressed.compress(self.payload) + self.compressed.flush() + enc.MARKER
        self.stem = "mojplaywin_20261020"

    def paths(self):
        directory = self.base / ".private-mojplaywin-offhost-backups"
        target = directory / (self.stem + "_mysql_gpgv2.gpg")
        manifest = directory / (self.stem + "_mysql_gpgv2.manifest.json")
        return target, manifest

    def store(self, payload=None):
        return enc.store(io.BytesIO(self.source if payload is None else payload), "mysql",
                         root=self.base, keyroot=self.base, minimum_free=0,
                         stem=self.stem, source_encoding="gzip-with-footer-v1")

    def decrypt_fixture(self, path):
        secret = self.base / ".config" / "mojplaywin-backup-recovery"
        key = enc.recovery_key(secret / "recovery-key.bin")
        proc = enc.gpg_process(key, secret / "gnupg-v2",
                               ["--decrypt", "--output", "-", str(path)],
                               input_pipe=False, stdout=subprocess.PIPE)
        data, _ = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 0)
        return data

    def test_authenticated_recovery_roundtrip_and_idempotence(self):
        status = self.store()
        archive, manifest = self.paths()
        self.assertTrue(status["decryption_verified"])
        self.assertFalse(status["release_permitted"])
        self.assertTrue(archive.is_file())
        meta = json.loads(manifest.read_text())
        self.assertEqual(meta["source_encoding"], "gzip-with-footer-v1")
        self.assertEqual(meta["uncompressed_source_bytes"], len(self.payload))
        self.assertFalse(meta["isolated_restoration_completed"])
        encoded = self.decrypt_fixture(archive)
        self.assertEqual(encoded, self.source)
        self.assertEqual(zlib.decompress(encoded[:-len(enc.MARKER)], wbits=31), self.payload)
        with self.assertRaises(RuntimeError):
            self.store()
        self.assertEqual(encoded, self.decrypt_fixture(archive))

    def test_truncated_gzip_never_completes(self):
        with self.assertRaises(RuntimeError):
            self.store(self.source[:-len(enc.MARKER)-7] + enc.MARKER)
        archive, manifest = self.paths()
        self.assertFalse(archive.exists())
        self.assertFalse(manifest.exists())

    def test_corrupt_gzip_crc_never_completes(self):
        corrupt = bytearray(self.source)
        corrupt[-len(enc.MARKER)-5] ^= 0x45
        with self.assertRaises(Exception):
            self.store(bytes(corrupt))
        archive, manifest = self.paths()
        self.assertFalse(archive.exists())
        self.assertFalse(manifest.exists())

    def test_unauthorized_gzip_append_never_completes(self):
        forged = self.source[:-len(enc.MARKER)] + b"garbage" + enc.MARKER
        with self.assertRaises(RuntimeError):
            self.store(forged)
        archive, manifest = self.paths()
        self.assertFalse(archive.exists())
        self.assertFalse(manifest.exists())

    def test_missing_marker_never_completes(self):
        with self.assertRaises(RuntimeError):
            self.store(self.source[:-len(enc.MARKER)])
        archive, manifest = self.paths()
        self.assertFalse(archive.exists())
        self.assertFalse(manifest.exists())

    def test_unexpected_archive_name_rejected(self):
        with self.assertRaises(RuntimeError):
            enc.store(io.BytesIO(self.source), "mysql", root=self.base,
                      keyroot=self.base, minimum_free=0, stem="../outside",
                      source_encoding="gzip-with-footer-v1")

    def test_independent_two_pass_recovery_reads_only_synthetic(self):
        self.store()
        self.assertFalse(recovery.both_ready(home=self.base))
        files_payload = b"synthetic tar fixture (not a customer file)\n" * 4000
        compressor = zlib.compressobj(1, zlib.DEFLATED, 31)
        files_source = compressor.compress(files_payload) + compressor.flush() + enc.MARKER
        enc.store(io.BytesIO(files_source), "files", root=self.base, keyroot=self.base,
                  minimum_free=0, stem=self.stem, source_encoding="gzip-with-footer-v1")
        self.assertTrue(recovery.both_ready(home=self.base))
        buffer = io.BytesIO()
        length = recovery.decode_archive("mysql", home=self.base, out=buffer)
        self.assertEqual(length, len(self.payload))
        self.assertEqual(buffer.getvalue(), self.payload)
        files_buffer = io.BytesIO()
        self.assertEqual(recovery.decode_archive("files", home=self.base, out=files_buffer),
                         len(files_payload))
        self.assertEqual(files_buffer.getvalue(), files_payload)

    def test_recovery_rejects_tampered_encrypted_archive_and_manifest(self):
        self.store()
        target, manifest = self.paths()
        damaged = bytearray(target.read_bytes())
        damaged[len(damaged)//2] ^= 1
        target.write_bytes(damaged)
        with self.assertRaises(Exception):
            recovery.decode_archive("mysql", home=self.base)
        # Even a correct ciphertext must not be accepted with a forged manifest.
        damaged[len(damaged)//2] ^= 1
        target.write_bytes(damaged)
        meta = json.loads(manifest.read_text())
        meta["uncompressed_source_bytes"] += 1
        manifest.write_text(json.dumps(meta))
        with self.assertRaises(RuntimeError):
            recovery.decode_archive("mysql", home=self.base)

    def test_traditional_gpg_backup_fixture_still_works(self):
        status = enc.store(io.BytesIO(b"older-format" * 200 + enc.MARKER), "files",
                           root=self.base, keyroot=self.base, minimum_free=0)
        self.assertEqual(status["source_encoding"], "raw-with-footer-v1")
        self.assertTrue(status["decryption_verified"])
        self.assertFalse(status["release_permitted"])


if __name__ == "__main__":
    unittest.main()
