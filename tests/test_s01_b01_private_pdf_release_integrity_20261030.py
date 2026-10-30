"""Offline regression checks for S-01 private B-01 release integrity gate."""
import hashlib
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "s01_b01_private_pdf_release_integrity_20261030.py"
spec = importlib.util.spec_from_file_location("s01_b01_private_pdf", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PrivatePdfIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "book.pdf"
        self.data = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
        self.pdf.write_bytes(self.data)
        self.sha = hashlib.sha256(self.data).hexdigest()

    def test_verified_file_does_not_grant_publication(self):
        verdict = gate.inspect_private_pdf(str(self.root), "book.pdf", self.sha)
        self.assertEqual(verdict["status"], "FILE_HASH_VERIFIED")
        self.assertFalse(verdict["safe_to_publish"])
        self.assertFalse(verdict["rights_approved"])
        self.assertFalse(verdict["checkout_verified"])

    def test_wrong_digest_fails_closed(self):
        with self.assertRaises(ValueError):
            gate.inspect_private_pdf(str(self.root), "book.pdf", "0" * 64)

    def test_symlink_and_hardlink_fail_closed(self):
        (self.root / "alias.pdf").symlink_to(self.pdf)
        with self.assertRaises(OSError):
            gate.inspect_private_pdf(str(self.root), "alias.pdf", self.sha)
        os.link(self.pdf, self.root / "hard.pdf")
        with self.assertRaises(ValueError):
            gate.inspect_private_pdf(str(self.root), "book.pdf", self.sha)

    def test_parent_symlink_and_traversal_fail_closed(self):
        real = self.root / "real"
        real.mkdir()
        (self.root / "link").symlink_to(real, target_is_directory=True)
        with self.assertRaises(OSError):
            gate.inspect_private_pdf(str(self.root), "link/book.pdf", self.sha)
        with self.assertRaises(ValueError):
            gate.inspect_private_pdf(str(self.root), "../book.pdf", self.sha)

    def test_corrupt_pdf_fails_closed_even_if_hash_matches(self):
        data = b"not-a-pdf-but-has-%%EOF-marker"
        self.pdf.write_bytes(data)
        with self.assertRaises(ValueError):
            gate.inspect_private_pdf(str(self.root), "book.pdf",
                                     hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
