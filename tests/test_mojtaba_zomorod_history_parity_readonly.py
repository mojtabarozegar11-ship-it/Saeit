"""Read-only legacy Zomorod SQLite lineage tests; fake private fixtures only."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts import mojtaba_zomorod_history_parity_readonly as lineage


INT_COLS = {
    "id", "enabled", "http_code", "duration_ms", "quality_score",
    "elapsed_ms", "last_artifact_id", "benchmark_before", "benchmark_after",
    "tests_passed", "accepted",
}


def fixture(home: Path) -> Path:
    db = home / lineage.RELATIVE
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        for table, cols in lineage.TABLES.items():
            spec = ", ".join(
                f'"{col}" {"INTEGER" if col in INT_COLS else "TEXT"}'
                for col in cols
            )
            conn.execute(f"CREATE TABLE {table} ({spec})")
        conn.execute("CREATE TABLE customers (email TEXT, amount INTEGER)")
        conn.execute("INSERT INTO customers VALUES ('private@example.test', 999)")
        values = {
            "id": 1, "code": "master", "agent_code": "master",
            "title": "PRIVATESAMPLE_SECRET_TITLE",
            "detail": "PRIVATESAMPLE_SECRET_DETAIL",
            "findings_json": '{"url":"PRIVATE_NEVER_ECHO"}',
        }
        for table, cols in lineage.TABLES.items():
            vals = [values.get(c, 1 if c in INT_COLS else ("hash" if c.endswith("_sha256") else "value"))
                    for c in cols]
            placeholders = ",".join("?" for _ in cols)
            conn.execute(f"INSERT INTO {table} VALUES ({placeholders})", vals)
    return db


class ZomorodHistoryLineageTests(unittest.TestCase):
    def test_all_five_full_tables_hashed_without_private_row_disclosure(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            fixture(home)
            report = lineage.scan(home=home)
            self.assertTrue(report["manifest_complete"], report)
            self.assertEqual(report["table_count"], 5)
            self.assertEqual(report["table_total_rows"], 5)
            self.assertEqual(set(report["tables"]), set(lineage.TABLES))
            self.assertFalse(report["database_modified"])
            self.assertFalse(report["rows_exported"])
            self.assertFalse(report["retirement_authorized"])
            self.assertNotIn("PRIVATESAMPLE", str(report))
            self.assertNotIn("private@example.test", str(report))

    def test_repeatable_manifests_and_comparison_of_independent_snapshots(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            fixture(Path(a))
            fixture(Path(b))
            left = lineage.scan(home=Path(a))
            right = lineage.scan(home=Path(b))
            self.assertEqual(left["lineage_sha256"], right["lineage_sha256"])
            parity = lineage.compare(left, right)
            self.assertTrue(parity["all_five_tables_equal"])
            self.assertFalse(parity["restore_procedure_verified"])
            self.assertFalse(parity["retirement_authorized"])

    def test_private_history_mutation_detected(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            fixture(Path(a))
            db_b = fixture(Path(b))
            with sqlite3.connect(db_b) as conn:
                conn.execute("UPDATE site_work_outputs SET title='DIFFERENT' WHERE id=1")
            left, right = lineage.scan(home=Path(a)), lineage.scan(home=Path(b))
            self.assertNotEqual(left["tables"]["site_work_outputs"],
                                right["tables"]["site_work_outputs"])
            self.assertFalse(lineage.compare(left, right)["records_equal"])

    def test_missing_history_table_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db = fixture(home)
            with sqlite3.connect(db) as conn:
                conn.execute("DROP TABLE site_work_generation_evidence")
            report = lineage.scan(home=home)
            self.assertEqual(report["state"], "incomplete_site_agent_history_tables")
            self.assertFalse(report["manifest_complete"])

    def test_schema_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db = fixture(home)
            with sqlite3.connect(db) as conn:
                conn.execute("ALTER TABLE runs ADD COLUMN new_private_payload TEXT")
            report = lineage.scan(home=home)
            self.assertEqual(report["state"], "legacy_history_schema_drift")

    def test_wal_or_journal_blocks_immutable_database_claims(self):
        for suffix in ("-wal", "-journal", "-shm"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                db = fixture(home)
                Path(str(db) + suffix).write_bytes(b"not a checkpointed snapshot")
                report = lineage.scan(home=home)
                self.assertEqual(report["state"],
                                 "sqlite_wal_or_journal_present_snapshot_unreliable")

    def test_symlink_to_database_and_parent_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db = fixture(home)
            target = home / "saved-copy"
            target.write_bytes(db.read_bytes())
            db.unlink()
            db.symlink_to(target)
            report = lineage.scan(home=home)
            self.assertEqual(report["state"], "missing_or_unsafe_site_database")
            self.assertFalse(report["retirement_authorized"])

    def test_absent_database_is_not_empty_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = lineage.scan(home=Path(tmp))
            self.assertEqual(report["state"], "missing_or_unsafe_site_database")

    def test_other_business_data_does_not_affect_agent_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db = fixture(home)
            before = lineage.scan(home=home)["lineage_sha256"]
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE customers SET email='changed@example.test'")
            after = lineage.scan(home=home)["lineage_sha256"]
            self.assertEqual(before, after)

    def test_row_id_change_detected_even_if_count_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            db = fixture(home)
            old = lineage.scan(home=home)
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE runs SET id=7 WHERE id=1")
            new = lineage.scan(home=home)
            self.assertEqual(old["table_total_rows"], new["table_total_rows"])
            self.assertNotEqual(old["lineage_sha256"], new["lineage_sha256"])

    def test_incomplete_manifest_cannot_claim_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            fixture(home)
            valid = lineage.scan(home=home)
            invalid = dict(valid, state="sqlite_changed_during_read")
            self.assertFalse(lineage.compare(valid, invalid)["records_equal"])
            self.assertFalse(lineage.compare(valid, invalid)["retirement_authorized"])


if __name__ == "__main__":
    unittest.main()
