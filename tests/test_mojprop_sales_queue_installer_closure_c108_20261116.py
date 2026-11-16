"""C108: no customer writes or deployment; prevent silent omission of owner CRM sales queue."""
from pathlib import Path
import unittest

from scripts import deploy_mojplaywin_moj_prop_backend as installer


ROOT = Path(__file__).resolve().parents[1]
QUEUE = Path("core/management/commands/mojprop_sales_action_queue.py")


class SalesQueueSourceClosureTests(unittest.TestCase):
    def test_sales_queue_is_installed_and_rollback_tracked_once(self):
        self.assertEqual(installer.FILES.count(QUEUE), 1)
        self.assertEqual(installer.REPLACE_FILES.count(QUEUE), 1)
        self.assertEqual(installer.ALL_FILES.count(QUEUE), 1)

    def test_source_exposes_exact_owner_queue_entrypoint(self):
        data = (ROOT / QUEUE).read_text(encoding="utf-8")
        self.assertIn("def action_queue_snapshot(", data)
        compile(data, str(QUEUE), "exec")

    def test_queue_is_preserved_with_browser_intake_and_signed_receipt(self):
        expected = (
            QUEUE,
            Path("core/mojprop_accessible_intake.py"),
            Path("core/mojprop_views.py"),
            Path("core/mojprop_receipts.py"),
        )
        for source in expected:
            with self.subTest(path=str(source)):
                self.assertIn(source, installer.ALL_FILES)
                self.assertIn(source, installer.REPLACE_FILES)
                self.assertTrue((ROOT / source).is_file())

    def test_release_keeps_independent_restore_gate(self):
        source = (ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text()
        self.assertIn("require_independent_db_restore(run_id, commit, staged_root)", source)
        self.assertIn('run_checked([str(python), "manage.py", "migrate"', source)
        self.assertIn("verify_backup_manifest(backup)", source)
        self.assertIn("restore(backup)", source)


if __name__ == "__main__":
    unittest.main()
