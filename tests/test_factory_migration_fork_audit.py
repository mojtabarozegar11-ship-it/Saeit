"""Dependency-free, non-mutating factory migration fork checks."""

import contextlib
import importlib.util
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_migration_fork_audit.py"
SPEC = importlib.util.spec_from_file_location("factory_migration_fork_audit", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FactoryMigrationForkAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.current = Path(self.temp.name) / "current"
        self.reference = Path(self.temp.name) / "reference"

    def add(self, root, name, dependencies=(), tail=""):
        folder = root / "core" / "migrations"
        folder.mkdir(parents=True, exist_ok=True)
        content = ("class Migration:\n"
                   f"    dependencies = {[( 'core', d) for d in dependencies]!r}\n"
                   "    operations = []\n" + tail)
        (folder / (name + ".py")).write_text(content, encoding="utf-8")

    def snapshot(self, names, with_migrations=True, with_task_fields=True):
        path = Path(self.temp.name) / "snapshot.sqlite3"
        with sqlite3.connect(path) as connection:
            if with_migrations:
                connection.execute("CREATE TABLE django_migrations "
                                   "(id INTEGER PRIMARY KEY, app TEXT, name TEXT)")
                connection.executemany(
                    "INSERT INTO django_migrations (app, name) VALUES ('core', ?)",
                    [(name,) for name in names])
            fields = ("factory_run_id INTEGER, product_id INTEGER, "
                      "environment TEXT, next_retry_at TEXT"
                      if with_task_fields else "status TEXT")
            connection.execute("CREATE TABLE core_agenttask (id INTEGER, " + fields + ")")
            connection.execute("CREATE TABLE core_product (id INTEGER)")
            connection.execute("CREATE TABLE core_factoryrun (id INTEGER)")
        return path

    def fork(self):
        for root in (self.current, self.reference):
            self.add(root, "0039_base")
        self.add(self.current, "0040_commerce", ("0039_base",))
        self.add(self.reference, "0040_factory", ("0039_base",))

    def test_identical_histories_remain_source_only(self):
        for root in (self.current, self.reference):
            self.add(root, "0039_base")
        result = module.audit(self.current, self.reference)
        self.assertEqual(result["status"], "no_source_fork_detected")
        self.assertEqual(result["identical_shared_count"], 1)
        self.assertFalse(result["production_ready"])
        self.assertFalse(result["database_schema_verified"])

    def test_parallel_number_forty_branches_are_blocked(self):
        for root in (self.current, self.reference):
            self.add(root, "0039_base")
        self.add(self.current, "0040_commerce", ("0039_base",))
        self.add(self.reference, "0040_factory", ("0039_base",))
        self.add(self.reference, "0041_next", ("0040_factory",))
        result = module.audit(self.current, self.reference)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["same_number_different_files"][0]["number"], "0040")
        self.assertEqual(result["current_only"], ["0040_commerce"])
        self.assertEqual(result["reference_only"], ["0040_factory", "0041_next"])

    def test_different_numbers_do_not_hide_divergent_branches(self):
        for root in (self.current, self.reference):
            self.add(root, "0039_base")
        self.add(self.current, "0040_commerce", ("0039_base",))
        self.add(self.reference, "0042_factory", ("0039_base",))
        result = module.audit(self.current, self.reference)
        self.assertEqual(result["same_number_different_files"], [])
        self.assertEqual(result["status"], "blocked")

    def test_missing_parent_fails_closed(self):
        self.add(self.current, "0040_orphan", ("0039_missing",))
        self.add(self.reference, "0040_orphan", ("0039_missing",))
        result = module.audit(self.current, self.reference)
        self.assertTrue(any(b["code"] == "MIGRATION_PARENT_MISSING"
                            for b in result["blockers"]))

    def test_invalid_python_fails_closed(self):
        folder = self.current / "core" / "migrations"
        folder.mkdir(parents=True)
        (folder / "0040_bad.py").write_text("class Migration(:\n", encoding="utf-8")
        self.add(self.reference, "0039_base")
        result = module.audit(self.current, self.reference)
        self.assertTrue(any(b["code"] == "MIGRATION_UNREADABLE"
                            for b in result["blockers"]))

    def test_source_scan_does_not_execute_migration_code(self):
        for root in (self.current, self.reference):
            self.add(root, "0039_base", tail="raise RuntimeError('must not execute')\n")
        result = module.audit(self.current, self.reference)
        self.assertEqual(result["status"], "no_source_fork_detected")

    def test_unshared_data_migration_is_flagged_for_manual_review(self):
        for root in (self.current, self.reference):
            self.add(root, "0039_base")
        folder = self.reference / "core" / "migrations"
        (folder / "0040_seed.py").write_text(
            "class Migration:\n"
            "    dependencies = [('core', '0039_base')]\n"
            "    operations = [migrations.RunPython(seed_records)]\n",
            encoding="utf-8")
        self.add(self.current, "0040_other", ("0039_base",))
        result = module.audit(self.current, self.reference)
        self.assertEqual(result["reference_unshared_data_operations"], [
            {"migration": "0040_seed", "operations": ["RunPython"]}])
        self.assertFalse(result["database_schema_verified"])

    def test_missing_history_never_passes(self):
        result = module.audit(self.current, self.reference)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(b["code"] == "MIGRATION_HISTORY_EMPTY"
                            for b in result["blockers"]))

    def test_disjoint_histories_never_pass(self):
        self.add(self.current, "0039_current")
        self.add(self.reference, "0040_reference")
        result = module.audit(self.current, self.reference)
        self.assertTrue(any(b["code"] == "MIGRATION_SHARED_ANCESTOR_MISSING"
                            for b in result["blockers"]))

    def test_cli_exit_code_blocks_on_fork(self):
        self.add(self.current, "0040_a")
        self.add(self.reference, "0040_b")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = module.main(["--current-root", str(self.current),
                                "--reference-root", str(self.reference)])
        self.assertEqual(code, 2)
        self.assertIn('"status": "blocked"', output.getvalue())

    def test_offline_snapshot_identifies_reference_migration_without_deploy_approval(self):
        self.fork()
        path = self.snapshot(["0039_base", "0040_factory"])
        report = module.audit(self.current, self.reference, path)
        evidence = report["sqlite_snapshot"]
        self.assertEqual(evidence["branch_evidence"], "reference_branch_only")
        self.assertEqual(evidence["applied_reference_only"], ["0040_factory"])
        self.assertEqual(evidence["unknown_applied"], [])
        self.assertEqual(evidence["applied_shared_count"], 1)
        self.assertEqual(evidence["agenttask_missing_worker_fields"], [])
        self.assertFalse(report["live_vps_verified"])
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["status"], "blocked")

    def test_offline_snapshot_identifies_mixed_fork_and_missing_worker_fields(self):
        self.fork()
        path = self.snapshot(["0039_base", "0040_commerce", "0040_factory",
                              "0041_unknown"], with_task_fields=False)
        evidence = module.audit(self.current, self.reference, path)["sqlite_snapshot"]
        self.assertEqual(evidence["branch_evidence"], "mixed_fork")
        self.assertEqual(evidence["unknown_applied"], ["0041_unknown"])
        self.assertEqual(evidence["agenttask_missing_worker_fields"], sorted(
            module.REQUIRED_TASK_FIELDS))

    def test_offline_snapshot_without_migration_table_fails_closed(self):
        self.fork()
        path = self.snapshot([], with_migrations=False)
        report = module.audit(self.current, self.reference, path)
        self.assertEqual(report["sqlite_snapshot"]["code"],
                         "SNAPSHOT_MIGRATION_TABLE_UNAVAILABLE")
        self.assertTrue(any(x["code"] == "SNAPSHOT_MIGRATION_TABLE_UNAVAILABLE"
                            for x in report["blockers"]))

    def test_offline_snapshot_symlink_and_journal_are_rejected(self):
        self.fork()
        path = self.snapshot(["0039_base"])
        linked = Path(self.temp.name) / "linked.sqlite3"
        linked.symlink_to(path)
        self.assertEqual(module.audit(self.current, self.reference, linked)[
            "sqlite_snapshot"]["code"], "SNAPSHOT_FILE_UNSAFE")
        sidecar = Path(str(path) + "-wal")
        sidecar.write_bytes(b"pending transaction marker")
        self.assertEqual(module.audit(self.current, self.reference, path)[
            "sqlite_snapshot"]["code"], "SNAPSHOT_JOURNAL_SIDECAR_PRESENT")

    def test_snapshot_cli_never_returns_release_success(self):
        self.fork()
        path = self.snapshot(["0039_base", "0040_factory"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = module.main(["--current-root", str(self.current),
                                "--reference-root", str(self.reference),
                                "--sqlite-snapshot", str(path)])
        self.assertEqual(code, 2)
        self.assertIn('"live_vps_verified": false', output.getvalue())
        self.assertIn('"branch_evidence": "reference_branch_only"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
