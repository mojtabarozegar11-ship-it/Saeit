"""Failure-injection regression for Moj Prop backend migration safety.

No hosting access, database restoration or production deployment occurs here.
"""
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer


class PostMigrationRollbackHoldTests(unittest.TestCase):
    def setUp(self):
        self.backup = Path("/not-a-real-production-backup")

    def test_pre_migration_failure_restores_files(self):
        with patch.object(installer, "restore") as restore:
            installer.recover_failed_deploy(
                self.backup, schema_migration_attempted=False
            )
            restore.assert_called_once_with(self.backup)

    def test_after_migration_attempt_refuses_file_only_restore(self):
        with patch.object(installer, "restore") as restore:
            with self.assertRaisesRegex(
                RuntimeError, "automatic source-only rollback DENIED"
            ):
                installer.recover_failed_deploy(
                    self.backup, schema_migration_attempted=True
                )
            restore.assert_not_called()

    def test_unverified_migration_state_cannot_default_to_safe(self):
        for flag in (None, 0, 1, "", "false", "true"):
            with self.subTest(flag=flag), patch.object(installer, "restore") as restore:
                with self.assertRaisesRegex(RuntimeError, "state is unverified"):
                    installer.recover_failed_deploy(
                        self.backup, schema_migration_attempted=flag
                    )
                restore.assert_not_called()

    def test_deployer_sets_unsafe_phase_before_migrate(self):
        source = (Path(__file__).resolve().parents[1]
                  / "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text()
        self.assertIn("schema_migration_attempted = False", source)
        start = source.index("def deploy(")
        marker = source.index("mark_schema_migration_started(backup)", start)
        phase = source.index("schema_migration_attempted = True", start)
        migrate = source.index('run_checked([str(python), "manage.py", "migrate"', start)
        failure = source.index("recover_failed_deploy(", migrate)
        self.assertLess(marker, phase)
        self.assertLess(phase, migrate)
        self.assertLess(migrate, failure)
        self.assertIn(
            "backup, schema_migration_attempted=schema_migration_attempted",
            source[failure:failure + 200],
        )


if __name__ == "__main__":
    unittest.main()
