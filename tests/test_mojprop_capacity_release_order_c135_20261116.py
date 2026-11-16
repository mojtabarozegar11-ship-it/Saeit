"""Source-only release ordering and packaging regressions: no live host or DB."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py"
WORKFLOW = ROOT / ".github/workflows/mojprop-backend-controlled-release-20261115.yml"
CAPACITY = Path("scripts/mojprop_restore_capacity_admission.py")


def fn(tree, name):
    return next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )


class RestoreSourceAdmissionOrdering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INSTALLER.read_text("utf-8")
        cls.tree = ast.parse(cls.source)

    def test_capacity_verifier_is_called_inside_existing_independent_db_gate(self):
        stage = fn(self.tree, "require_independent_db_restore")
        calls = [
            (n.lineno, ast.unparse(n.func))
            for n in ast.walk(stage)
            if isinstance(n, ast.Call)
        ]
        proof = [line for line, name in calls
                 if name == "verify_database_restore_evidence"]
        capacity = [line for line, name in calls
                    if name == "require_signed_capacity_receipt"]
        self.assertEqual(len(proof), 1)
        self.assertEqual(len(capacity), 1)
        self.assertLess(proof[0], capacity[0])
        self.assertIn('snapshot_sha256=verified["snapshot_sha256"]',
                      ast.get_source_segment(self.source, stage))

    def test_signed_capacity_is_a_prerequisite_of_first_live_file_write(self):
        deploy = fn(self.tree, "deploy")
        calls = [(n.lineno, ast.unparse(n.func))
                 for n in ast.walk(deploy) if isinstance(n, ast.Call)]
        guard = [line for line, name in calls
                 if name == "require_independent_db_restore"]
        mkdir = [line for line, name in calls if name == "backup.mkdir"]
        self.assertEqual(len(guard), 1)
        self.assertEqual(len(mkdir), 1)
        self.assertLess(guard[0], mkdir[0])

    def test_reviewed_0047_target_is_not_downgraded(self):
        self.assertIn('migration_target = "0047_mpw_guest_email_recovery"',
                      self.source)
        self.assertIn('"core", migration_target, "--noinput"', self.source)
        self.assertIn("mark_schema_migration_started(backup)", self.source)

    def test_guard_is_staged_but_not_copied_into_production_tree(self):
        from scripts import deploy_mojplaywin_moj_prop_backend as tool
        self.assertIn(CAPACITY, tool.ALL_FILES)
        self.assertNotIn(CAPACITY, tool.REPLACE_FILES)

    def test_guard_is_in_source_syntax_gate(self):
        workflow = WORKFLOW.read_text("utf-8")
        line = next(
            line for line in workflow.splitlines()
            if line.lstrip().startswith("python3 -m py_compile ")
        )
        self.assertIn(str(CAPACITY), line)

    def test_guard_is_in_actual_release_tar_bundle(self):
        workflow = WORKFLOW.read_text("utf-8")
        line = next(
            line for line in workflow.splitlines()
            if 'tar -cf "$RUNNER_TEMP/moj-prop-catalog.tar"' in line
        )
        self.assertIn(str(CAPACITY), line)

    def test_manual_owner_and_backup_release_flags_remain(self):
        workflow = WORKFLOW.read_text("utf-8")
        for phrase in (
            "workflow_dispatch:",
            "inputs.owner_approval == 'OWNER_APPROVED'",
            "MOJPROP_BACKUP_RESTORE_VERIFIED",
            "MOJPROP_ROLLBACK_VERIFIED",
            "MOJPROP_TENANT_ISOLATION_VERIFIED",
        ):
            self.assertIn(phrase, workflow)
        self.assertNotIn("on: push", workflow)

    def test_readonly_check_does_not_claim_remote_restore(self):
        source = (ROOT / CAPACITY).read_text("utf-8")
        self.assertIn(
            '"actual_remote_restore_independently_observed_by_this_code": False',
            source
        )
        self.assertIn('"release_authorized": False', source)


if __name__ == "__main__":
    unittest.main()
