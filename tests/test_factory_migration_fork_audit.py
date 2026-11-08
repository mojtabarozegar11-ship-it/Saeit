"""Dependency-free, non-mutating factory migration fork checks."""

import contextlib
import importlib.util
import io
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
