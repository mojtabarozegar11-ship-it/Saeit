"""Synthetic-only regression for isolated off-host SQLite rehearsal."""
import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from f01_offhost_sqlite_backup_verify import Blocked, verify

class VerifyTest(unittest.TestCase):
    def test_good_backup_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "backup.sqlite3"
            db = sqlite3.connect(p)
            db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO sample(value) VALUES (?)", ("synthetic",))
            db.commit()
            db.close()
            original = p.read_bytes()
            result = verify(p, hashlib.sha256(original).hexdigest(), d)
            self.assertEqual(result["status"], "ISOLATED_COPY_INTEGRITY_VERIFIED")
            self.assertEqual(p.read_bytes(), original)
            self.assertFalse(result["production_restore_proved"])
            self.assertFalse(result["deployment_authorized"])

    def test_wrong_digest(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "backup.sqlite3"
            db = sqlite3.connect(p)
            db.execute("CREATE TABLE sample (id)")
            db.close()
            with self.assertRaisesRegex(Blocked, "SHA256_MISMATCH"):
                verify(p, "0" * 64, d)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "backup.sqlite3"
            p.write_bytes(b"X" * 1024)
            q = Path(d) / "link.sqlite3"
            q.symlink_to(p)
            with self.assertRaisesRegex(Blocked, "LINKED_PATH"):
                verify(q, "0" * 64, d)

    def test_digest_required(self):
        with self.assertRaisesRegex(Blocked, "EXPECTED_SHA256_REQUIRED"):
            verify("/missing", "", None)

    def test_non_sqlite_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "invalid"
            p.write_bytes(b"X" * 1024)
            with self.assertRaisesRegex(Blocked, "NOT_SQLITE"):
                verify(p, hashlib.sha256(p.read_bytes()).hexdigest(), d)

if __name__ == "__main__":
    unittest.main()
