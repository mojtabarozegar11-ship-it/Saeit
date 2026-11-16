"""Source-only regression: restore proof must precede the first live backend backup.

No production host, Django database, network, customer record, payment or
environment secret is accessed by this test.
"""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py"


class RestoreGateOrderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(INSTALLER.read_text(encoding="utf-8"))
        cls.deploy = next(
            node for node in cls.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "deploy"
        )

    def test_restore_evidence_is_called_before_first_backup_directory_creation(self):
        calls = [
            (node.lineno, ast.unparse(node.func))
            for node in ast.walk(self.deploy)
            if isinstance(node, ast.Call)
        ]
        evidence = [line for line, name in calls if name == "require_independent_db_restore"]
        backup_mkdir = [
            line for line, name in calls
            if name == "backup.mkdir"
        ]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(len(backup_mkdir), 1)
        self.assertLess(evidence[0], backup_mkdir[0])

    def test_schema_closure_precedes_restore_evidence_and_backup(self):
        calls = {
            ast.unparse(node.func): node.lineno
            for node in ast.walk(self.deploy)
            if isinstance(node, ast.Call)
        }
        for name in ("check_schema_closure", "require_independent_db_restore", "backup.mkdir"):
            self.assertIn(name, calls)
        self.assertLess(calls["check_schema_closure"], calls["require_independent_db_restore"])
        self.assertLess(calls["require_independent_db_restore"], calls["backup.mkdir"])

    def test_no_unscoped_migration_command(self):
        source = ast.get_source_segment(INSTALLER.read_text(encoding="utf-8"), self.deploy)
        self.assertIn('"core", migration_target, "--noinput"', source)
        self.assertNotIn('"manage.py", "migrate", "--noinput"', source)

    def test_release_target_is_current_reviewed_0047(self):
        assignments = [
            node for node in ast.walk(self.deploy)
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "migration_target" for t in node.targets)
        ]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(ast.literal_eval(assignments[0].value), "0047_mpw_guest_email_recovery")


if __name__ == "__main__":
    unittest.main()
