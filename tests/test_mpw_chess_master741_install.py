"""Self-contained integrity tests; never connects to a live store."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scripts import mpw_chess_master741_install as handoff


class PrivateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.source = base / "incoming.pdf"
        self.private_root = base / "private"
        self.private_root.mkdir(mode=0o700)
        self.target = self.private_root / "store/chess-improvement/master.pdf"
        self.bytes = b"%PDF-1.4\n% fake local fixture, never a production ebook\n%%EOF\n"
        self.source.write_bytes(self.bytes)
        values = {
            "SOURCE": self.source,
            "PRIVATE_ROOT": self.private_root,
            "TARGET": self.target,
            "EXPECTED_SIZE": len(self.bytes),
            "EXPECTED_SHA256": hashlib.sha256(self.bytes).hexdigest(),
        }
        for key, value in values.items():
            patcher = patch.object(handoff, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_hash_and_size(self):
        self.assertEqual(handoff.verify(self.source), hashlib.sha256(self.bytes).hexdigest())

    def test_no_source_rejected(self):
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, "PRIVATE_PDF_MISSING"):
            handoff.install_file()

    def test_wrong_source_sha_rejected(self):
        self.source.write_bytes(b"%PDF-9.9" + self.bytes[8:])
        with self.assertRaisesRegex(ValueError, "SHA256"):
            handoff.install_file()

    def test_symlink_input_rejected(self):
        self.source.unlink()
        self.source.symlink_to(self.private_root)
        with self.assertRaisesRegex(ValueError, "PRIVATE_PDF_MISSING"):
            handoff.verify(self.source)

    def test_private_copy_idempotent(self):
        self.assertEqual(handoff.install_file(), hashlib.sha256(self.bytes).hexdigest())
        self.assertEqual(self.target.read_bytes(), self.bytes)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(handoff.install_file(), hashlib.sha256(self.bytes).hexdigest())

    def test_conflicting_target_not_overwritten(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"different")
        with self.assertRaises(ValueError):
            handoff.install_file()
        self.assertEqual(self.target.read_bytes(), b"different")


if __name__ == "__main__":
    unittest.main()
