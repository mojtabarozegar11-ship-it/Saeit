"""Synthetic-only, no production access for one failed VPS GPG-partial cleanup."""
import os
import tempfile
import time
import unittest
from pathlib import Path

from scripts.mpw_vps_cleanup_failed_partial_20261102 import inspect_or_remove

NAME = "mojplaywin_20261102T044200Z_0123456789abcdef_mysql_gpgv2.gpg.partial"


class FailedPartialCleanupTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.home = Path(t.name)
        self.root = self.home / ".private-mojplaywin-offhost-backups"
        self.root.mkdir(mode=0o700)
        self.partial = self.root / NAME
        self.partial.write_bytes(b"synthetic partial ciphertext only")
        self.partial.chmod(0o600)
        old = time.time() - 3600
        os.utime(self.partial, (old, old))
        self.expected = self.partial.stat().st_size

    def probe(self, execute=False):
        return inspect_or_remove(self.home, execute=execute,
                                 expected_bytes=self.expected)

    def test_audit_is_read_only_and_does_not_reveal_name(self):
        result = self.probe()
        self.assertFalse(result["deleted"])
        self.assertEqual(result["approved_partial_bytes"], self.expected)
        self.assertTrue(self.partial.exists())
        self.assertNotIn(NAME, str(result))

    def test_only_explicit_single_partial_removed(self):
        complete = self.root / "other_valid_backup.gpg"
        complete.write_bytes(b"untouched valid fixture")
        result = self.probe(execute=True)
        self.assertTrue(result["deleted"])
        self.assertFalse(self.partial.exists())
        self.assertEqual(complete.read_bytes(), b"untouched valid fixture")
        with self.assertRaises(RuntimeError):
            self.probe(execute=True)

    def test_completed_sibling_refuses_delete(self):
        sibling = self.root / NAME.replace(".gpg.partial", ".gpg")
        sibling.write_bytes(b"real archive remains")
        with self.assertRaises(RuntimeError):
            self.probe(execute=True)
        self.assertTrue(self.partial.exists())

    def test_wrong_size_or_multiple_partials_refuse(self):
        with self.assertRaises(RuntimeError):
            inspect_or_remove(self.home, execute=True,
                              expected_bytes=self.expected + 1)
        extra = self.root / NAME.replace("0123456789abcdef", "1111111111111111")
        extra.write_bytes(b"other partial")
        with self.assertRaises(RuntimeError):
            self.probe(execute=True)
        self.assertTrue(self.partial.exists())

    def test_symlink_and_hardlink_refuse(self):
        self.partial.unlink()
        external = self.home / "external"
        external.write_bytes(b"outside")
        self.partial.symlink_to(external)
        with self.assertRaises(RuntimeError):
            self.probe(execute=True)
        self.partial.unlink()
        self.partial.write_bytes(b"synthetic partial ciphertext only")
        self.partial.chmod(0o600)
        old = time.time() - 3600
        os.utime(self.partial, (old, old))
        other = self.home / "hardlink"
        os.link(self.partial, other)
        with self.assertRaises(RuntimeError):
            self.probe(execute=True)

    def test_recent_file_and_public_directory_refuse(self):
        os.utime(self.partial, None)
        with self.assertRaises(RuntimeError):
            self.probe(execute=True)
        self.root.chmod(0o755)
        with self.assertRaises(RuntimeError):
            self.probe(execute=True)


if __name__ == "__main__":
    unittest.main()
