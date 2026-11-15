"""Legacy Moj Prop release must deny new commercial migrations before touching live state."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer


class ObsoleteCommercialBackendReleaseTests(TestCase):
    def test_each_post_0041_migration_blocks_old_installer(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in installer.COMMERCIAL_SCHEMA_MIGRATIONS:
                with self.subTest(migration=str(relative)):
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# new migration\n", encoding="utf-8")
                    with self.assertRaisesRegex(RuntimeError, "COMMERCIAL_DB_UPGRADE_BLOCKED"):
                        installer.require_legacy_installer_compatibility(root)
                    path.unlink()

    def test_an_old_0041_only_snapshot_remains_compatible_with_legacy_gate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            migration = root / "core/migrations/0041_mojprop_request.py"
            migration.parent.mkdir(parents=True)
            migration.write_text("# legacy schema only\n", encoding="utf-8")
            installer.require_legacy_installer_compatibility(root)

    def test_symlink_migration_cannot_bypass_scope_detection(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            migration = root / installer.COMMERCIAL_SCHEMA_MIGRATIONS[0]
            migration.parent.mkdir(parents=True)
            migration.symlink_to(root / "not_present.py")
            with self.assertRaisesRegex(RuntimeError, "COMMERCIAL_DB_UPGRADE_BLOCKED"):
                installer.require_legacy_installer_compatibility(root)

    def test_deploy_denies_commercial_schema_before_backup_or_migration(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            staging, live, docroot, backups = (
                base / "staged", base / "live", base / "site", base / "backups"
            )
            staging.mkdir()
            live.mkdir()
            docroot.mkdir()
            (docroot / "passenger_wsgi.py").write_text(
                "from Saeit-staging import app\n", encoding="utf-8"
            )
            for item in installer.ALL_FILES:
                path = staging / item
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# staged\n", encoding="utf-8")
            migration = staging / installer.COMMERCIAL_SCHEMA_MIGRATIONS[0]
            migration.parent.mkdir(parents=True, exist_ok=True)
            migration.write_text("# commercial database schema\n", encoding="utf-8")
            with (
                patch.object(installer, "ROOT", live),
                patch.object(installer, "DOCROOT", docroot),
                patch.object(installer, "BACKUP_ROOT", backups),
                patch.object(installer, "run_checked") as command,
                patch.object(installer, "restart_passenger") as restart,
            ):
                with self.assertRaisesRegex(RuntimeError, "COMMERCIAL_DB_UPGRADE_BLOCKED"):
                    installer.deploy("12345", "a" * 40, staging)
                command.assert_not_called()
                restart.assert_not_called()
            self.assertFalse(backups.exists())
