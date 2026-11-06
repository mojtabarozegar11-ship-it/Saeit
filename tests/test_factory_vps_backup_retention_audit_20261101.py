"""Synthetic regression tests for read-only factory backup inventory."""
import importlib.util
import json
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock
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
        self.assertGreaterEqual(report["records"][0]["check_elapsed_seconds"], 0)
        self.assertTrue(report["records"][0]["quick_check_ok"])
        self.assertFalse(report["records"][0]["approved_for_deletion"])
        self.assertTrue(report["deletion_gate"].startswith("BLOCKED_"))

    def test_total_budget_marks_unchecked_as_unknown_and_never_delete(self):
        path = self.make_database("master-before-20261027T000000Z.sqlite3")
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        with mock.patch.object(audit_module, "MAX_TOTAL_VERIFICATION_SECONDS", 0):
            report = audit_module.audit(self.root)
        row = report["records"][0]
        self.assertEqual(report["verification_skipped_budget_count"], 1)
        self.assertEqual(row["check_result"], "global_verification_budget_exhausted")
        self.assertFalse(row["quick_check_ok"])
        self.assertFalse(row["approved_for_deletion"])
        self.assertFalse(report["offsite_functional_restore_verified"])
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_verification_checks_newest_snapshot_before_older_backups(self):
        older = self.make_database("master-before-20261025T000000Z.sqlite3")
        newer = self.make_database("master-before-20261027T000000Z.sqlite3")
        import os
        import time
        now = time.time() - 120
        os.utime(older, (now - 20, now - 20))
        os.utime(newer, (now - 10, now - 10))
        checked = []
        def fake_check(path, seconds):
            checked.append(path.name)
            return True, "quick_check_ok"
        with mock.patch.object(audit_module, "check_database", side_effect=fake_check):
            report = audit_module.audit(self.root)
        self.assertEqual(checked, [newer.name, older.name])
        self.assertEqual(report["verified_exact_master_count"], 2)

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

    def test_nested_snapshots_are_inventory_only_not_master_keep_candidates(self):
        top = self.make_database("master-before-20261027T000000Z.sqlite3")
        nested_dir = self.root / "archive"
        nested_dir.mkdir()
        nested = self.make_database("master-before-20261028T000000Z.sqlite3")
        nested.rename(nested_dir / nested.name)
        report = audit_module.audit(self.root)
        self.assertEqual(report["sqlite_count"], 2)
        self.assertEqual(report["verified_exact_master_count"], 1)
        self.assertEqual(report["keep_newest_two_verified_master_paths"], [top.name])
        nested_record = next(
            row for row in report["records"]
            if row["path_relative"].startswith("archive/")
        )
        self.assertTrue(nested_record["quick_check_ok"])
        self.assertFalse(nested_record["exact_master_before_name"])
        self.assertFalse(nested_record["approved_for_deletion"])

    def test_newest_selection_uses_exact_mtime_not_rounded_age(self):
        a = self.make_database("master-before-20261025T000000Z.sqlite3")
        b = self.make_database("master-before-20261026T000000Z.sqlite3")
        c = self.make_database("master-before-20261027T000000Z.sqlite3")
        import os
        import time
        now = time.time() - 60
        os.utime(a, (now - 3, now - 3))
        os.utime(b, (now - 2, now - 2))
        os.utime(c, (now - 1, now - 1))
        report = audit_module.audit(self.root)
        self.assertEqual(len({r["age_days"] for r in report["records"]}), 1)
        self.assertEqual(
            set(report["keep_newest_two_verified_master_paths"]),
            {b.name, c.name},
        )

    def test_timed_out_quick_check_distinguished_from_corruption(self):
        path = self.make_database("master-before-20261027T141414Z.sqlite3")
        with sqlite3.connect(path) as conn:
            conn.executemany(
                "INSERT INTO example(note) VALUES (?)",
                (("synthetic",) for _ in range(4000)),
            )
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        healthy, result = audit_module.check_database(path, seconds=-1)
        self.assertFalse(healthy)
        self.assertEqual(result, "quick_check_timed_out")
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_blocked_sqlite_io_child_is_killed_at_wall_clock_timeout(self):
        path = self.make_database("master-before-20261027T151515Z.sqlite3")
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        with mock.patch.object(
            audit_module.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd="read_only_sqlite", timeout=0.01),
        ) as run:
            healthy, reason = audit_module.check_database(path, seconds=0.01)
        self.assertFalse(healthy)
        self.assertEqual(reason, "quick_check_timed_out")
        self.assertEqual(run.call_args.kwargs["timeout"], 0.01)
        self.assertEqual(run.call_args.args[0][1:3], ["-B", "-c"])
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_wal_or_journal_sidecar_blocks_snapshot_verification(self):
        path = self.make_database("master-before-20261027T121212Z.sqlite3")
        wal = Path(str(path) + "-wal")
        wal.write_bytes(b"uncheckpointed-placeholder")
        before = wal.read_bytes()
        report = audit_module.audit(self.root)
        self.assertFalse(report["records"][0]["quick_check_ok"])
        self.assertEqual(report["records"][0]["check_result"], "sqlite_sidecar_present")
        self.assertEqual(wal.read_bytes(), before)

    def test_immutable_quick_check_creates_no_sidecar_files(self):
        path = self.make_database("master-before-20261027T131313Z.sqlite3")
        report = audit_module.audit(self.root)
        self.assertTrue(report["records"][0]["quick_check_ok"])
        for suffix in ("-wal", "-shm", "-journal"):
            self.assertFalse(Path(str(path) + suffix).exists())

    def test_public_report_redacts_root_and_relative_paths(self):
        path = self.make_database("master-before-20261027T000000Z.sqlite3")
        report = audit_module.audit(self.root)
        public = audit_module.public_report(report)
        encoded = json.dumps(public, sort_keys=True)
        self.assertEqual(public["backup_root"], "(redacted-fixed-root)")
        self.assertNotIn(str(self.root.resolve()), encoded)
        self.assertNotIn("path_relative", encoded)
        self.assertEqual(len(public["backup_root_sha256_prefix"]), 16)
        self.assertEqual(public["records"][0]["filename"], path.name)


    def test_factory_operations_inventory_is_read_only_and_redacted(self):
        operations = Path(self.tmp.name) / "operations"
        backups = operations / "backups"
        archives = operations / "archives"
        backups.mkdir(parents=True)
        archives.mkdir()
        archived = archives / "historic-complete.log"
        archived.write_bytes(b"archived")
        small = backups / "older-build.tmp"
        small.write_bytes(b"x" * 40)
        before = (archived.read_bytes(), archived.stat().st_mtime_ns)
        result = audit_module.inventory_factory_operations(operations)
        self.assertTrue(result["root_present"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["files_changed_or_deleted"], 0)
        self.assertEqual(result["files_scanned"], 2)
        self.assertEqual(result["bytes_total"], 48)
        self.assertEqual(result["by_area"]["archives"]["bytes"], 8)
        self.assertEqual(result["by_extension"][".tmp"]["files"], 1)
        self.assertEqual(before, (archived.read_bytes(), archived.stat().st_mtime_ns))
        self.assertNotIn("historic-complete.log", json.dumps(result))

    def test_factory_operations_inventory_rejects_symlink_root(self):
        operations = Path(self.tmp.name) / "operations"
        operations.mkdir()
        linked = Path(self.tmp.name) / "operations-link"
        linked.symlink_to(operations, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            audit_module.inventory_factory_operations(linked)


if __name__ == "__main__":
    unittest.main()
