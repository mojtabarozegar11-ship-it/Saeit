"""Synthetic regression tests for read-only factory backup inventory."""
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "factory_vps_backup_retention_audit_20261101.py"
spec = importlib.util.spec_from_file_location("factory_backup_audit", MODULE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class FactoryBackupAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "backups"
        self.root.mkdir()

    def make_database(self, name):
        path = self.root / name
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE example (id INTEGER PRIMARY KEY, note TEXT)")
            conn.execute("INSERT INTO example(note) VALUES ('protected')")
        return path

    def test_lists_snapshot_without_touching_it(self):
        path = self.make_database("master-before-20261027T000000Z.sqlite3")
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        report = audit_module.audit(self.root)
        after = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertEqual(before, after)
        self.assertTrue(report["read_only"])
        self.assertEqual(report["files_changed_or_deleted"], 0)
        self.assertEqual(report["sqlite_count"], 1)
        self.assertTrue(report["records"][0]["quick_check_ok"])
        self.assertFalse(report["records"][0]["approved_for_deletion"])
        self.assertTrue(report["deletion_gate"].startswith("BLOCKED_"))

    def test_corrupt_file_never_approved(self):
        path = self.root / "master-before-20261026T000000Z.sqlite3"
        path.write_bytes(b"corrupted backup")
        report = audit_module.audit(self.root)
        self.assertFalse(report["records"][0]["quick_check_ok"])
        self.assertEqual(report["records"][0]["check_result"], "not_sqlite_header")
        self.assertEqual(path.read_bytes(), b"corrupted backup")

    def test_symlink_root_rejected(self):
        linked = Path(self.tmp.name) / "link"
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            audit_module.audit(linked)

    def test_symlinked_file_skipped(self):
        real = self.make_database("master-before-20261028T000000Z.sqlite3")
        (self.root / "master-before-20261025T000000Z.sqlite3").symlink_to(real)
        report = audit_module.audit(self.root)
        self.assertEqual(report["sqlite_count"], 1)

    def test_two_newest_verified_marked_keep_only(self):
        a = self.make_database("master-before-20261025T000000Z.sqlite3")
        b = self.make_database("master-before-20261026T000000Z.sqlite3")
        c = self.make_database("master-before-20261027T000000Z.sqlite3")
        import os
        now = max(a.stat().st_mtime_ns, b.stat().st_mtime_ns, c.stat().st_mtime_ns) / 1e9
        for offset, path in enumerate((a, b, c)):
            os.utime(path, (now - 86400 * (3 - offset),) * 2)
        report = audit_module.audit(self.root)
        self.assertEqual(report["sqlite_count"], 3)
        self.assertEqual(
            set(report["keep_newest_two_verified_master_paths"]),
            {b.name, c.name},
        )
        self.assertTrue(all(not r["approved_for_deletion"] for r in report["records"]))


if __name__ == "__main__":
    unittest.main()
