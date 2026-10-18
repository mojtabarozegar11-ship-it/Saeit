"""Synthetic-only tests: complete encrypted chunk set, resume, corruption, restore."""
import os
import stat
import tempfile
import unittest
from pathlib import Path

try:
    from scripts.mojplaywin_chunked_encrypted_snapshot import stage, verify, restore
    HAS_CRYPTOGRAPHY = True
except ModuleNotFoundError as exc:
    if exc.name != "cryptography":
        raise
    HAS_CRYPTOGRAPHY = False


@unittest.skipUnless(HAS_CRYPTOGRAPHY, "Standalone crypto test runs in dedicated CI with cryptography installed")
class ChunkedEncryptedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mjwp-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root / "key.bin"
        fd = os.open(str(self.key), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(os.urandom(32))
        self.source = self.root / "FAKE.bin"
        self.plain = os.urandom(2 * 1024 * 1024 + 1700)
        self.source.write_bytes(self.plain)
        self.staging = self.root / "encrypted-chunks"

    def test_verified_complete_and_private_restore(self):
        status = stage(self.source, self.staging, "fixture-001", self.key, 1024 * 1024)
        self.assertEqual(status["status"], "verified_complete")
        self.assertEqual(status["chunks"], 3)
        self.assertTrue(verify(self.staging, "fixture-001", self.key)["verified"])
        self.assertFalse((self.staging / "fixture-001" / "plan.json").stat().st_mode & stat.S_IROTH)
        recovered = self.root / "restore.bin"
        self.assertTrue(restore(self.staging, "fixture-001", self.key, recovered)["verified_restoration"])
        self.assertEqual(recovered.read_bytes(), self.plain)
        with self.assertRaises(ValueError):
            restore(self.staging, "fixture-001", self.key, recovered)

    def test_resume_skips_verified_prior_cipher_chunks(self):
        stage(self.source, self.staging, "fixture-002", self.key, 1024 * 1024)
        folder = self.staging / "fixture-002"
        first = (folder / "part-000000.bin").read_bytes()
        second = (folder / "part-000001.bin").read_bytes()
        (folder / "manifest.json").unlink()  # Simulate crash before final commit.
        (folder / "part-000002.bin").unlink()
        status = stage(self.source, self.staging, "fixture-002", self.key, 1024 * 1024)
        self.assertEqual(status["status"], "verified_complete")
        self.assertEqual((folder / "part-000000.bin").read_bytes(), first)
        self.assertEqual((folder / "part-000001.bin").read_bytes(), second)
        self.assertTrue(verify(self.staging, "fixture-002", self.key)["verified"])

    def test_tampered_ciphertext_and_metadata_fail_closed(self):
        stage(self.source, self.staging, "fixture-003", self.key, 1024 * 1024)
        folder = self.staging / "fixture-003"
        path = folder / "part-000000.bin"
        blob = bytearray(path.read_bytes())
        blob[-1] ^= 1
        path.write_bytes(blob)
        with self.assertRaises(ValueError):
            verify(self.staging, "fixture-003", self.key)
        with self.assertRaises(ValueError):
            stage(self.source, self.staging, "fixture-003", self.key, 1024 * 1024)

    def test_source_mutation_and_wrong_key_cannot_resume(self):
        stage(self.source, self.staging, "fixture-004", self.key, 1024 * 1024)
        other_key = self.root / "other-key.bin"
        fd = os.open(str(other_key), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(os.urandom(32))
        with self.assertRaises(ValueError):
            verify(self.staging, "fixture-004", other_key)
        self.source.write_bytes(self.plain + b"tamper")
        with self.assertRaises(ValueError):
            stage(self.source, self.staging, "fixture-004", self.key, 1024 * 1024)

    def test_refuse_non_private_key_and_symlink_root(self):
        os.chmod(self.key, 0o644)
        with self.assertRaises(ValueError):
            stage(self.source, self.staging, "fixture-005", self.key, 1024 * 1024)
        os.chmod(self.key, 0o600)
        link = self.root / "link-root"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            stage(self.source, link, "fixture-005", self.key, 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
