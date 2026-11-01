"""Regression: generic cPanel deploy must fail before mutating an unready DB."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "cpanel_deploy.sh"


class SafeOfficeDeployOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = DEPLOY.read_text(encoding="utf-8")
        cls.commands = [
            line.strip()
            for line in cls.script.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_shell_fail_closed(self):
        self.assertIn("set -euo pipefail", self.commands)

    def test_no_automatic_migration(self):
        migrations = [line for line in self.commands if re.search(r"manage\.py\s+migrate\b", line)]
        self.assertEqual(migrations, ['"$PYTHON" manage.py migrate --check'])
        self.assertNotIn("--fake", self.script)

    def test_read_only_checks_precede_runtime_cutover(self):
        preflight = self.commands.index('"$PYTHON" manage.py migrate --check')
        readiness = self.commands.index('"$PYTHON" manage.py production_gate')
        collect = self.commands.index('"$PYTHON" manage.py collectstatic --noinput')
        restart = self.commands.index("touch passenger_wsgi.py")
        self.assertLess(preflight, readiness)
        self.assertLess(readiness, collect)
        self.assertLess(collect, restart)

    def test_no_silent_gate_bypass(self):
        self.assertEqual(self.commands.count('"$PYTHON" manage.py production_gate'), 1)
        self.assertNotIn("|| true", self.script)


class PrivateOfficeReleaseWorkflowRegression(unittest.TestCase):
    """The old staff login fallback must never patch live Passenger on merge."""

    def test_legacy_login_patcher_removed(self):
        workflow = (ROOT / ".github/workflows/zomorod-office-login-route-release.yml").read_text(encoding="utf-8")
        self.assertNotIn("\n  release:\n", workflow)
        self.assertNotIn("passenger.touch()", workflow)
        self.assertNotIn('RedirectView.as_view(url="/admin/login/?next=/staff/command-center/", permanent=False)', workflow)
        self.assertIn("HOST_OR_DB_MUTATION=none", workflow)

    def test_readonly_diagnostic_targets_exact_head_and_tolerates_stage_race(self):
        diag = (ROOT / ".github/workflows/zomorod-office-500-readonly-diagnostic.yml").read_text(encoding="utf-8")
        stage = (ROOT / ".github/workflows/zomorod-messaging-private-staging.yml").read_text(encoding="utf-8")
        self.assertIn("SOURCE_SHA: ${{ github.event.pull_request.head.sha }}", diag)
        self.assertIn("EXACT_HEAD_PRIVATE_STAGE=missing", diag)
        self.assertIn("EXACT_HEAD_PRIVATE_STAGE=verified", diag)
        self.assertIn('os.environ["COMPANY_MESSAGING_SEND_ENABLED"]="false"', diag)
        self.assertIn('".github/workflows/zomorod-office-500-readonly-diagnostic.yml"', stage)
        self.assertIn("DB_CLASSIFICATION_READONLY=true", diag)
        self.assertIn("ACCOUNTING_SOURCE_OF_TRUTH_NOT_ATTESTED=true", diag)



class ReadOnlySQLitePreflightTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)

    def test_missing_database_is_not_created(self):
        from scripts.production_db_readonly_preflight import PreflightFailure, inspect_sqlite_file
        missing = self.base / "missing.sqlite3"
        with self.assertRaisesRegex(PreflightFailure, "SQLITE_MISSING"):
            inspect_sqlite_file(missing, self.base)
        self.assertFalse(missing.exists())

    def test_zero_length_database_is_blocked(self):
        from scripts.production_db_readonly_preflight import PreflightFailure, inspect_sqlite_file
        database = self.base / "empty.sqlite3"
        database.touch()
        with self.assertRaisesRegex(PreflightFailure, "SQLITE_EMPTY"):
            inspect_sqlite_file(database, self.base)
        self.assertEqual(database.stat().st_size, 0)

    def test_corrupt_header_is_blocked(self):
        from scripts.production_db_readonly_preflight import PreflightFailure, inspect_sqlite_file
        database = self.base / "corrupt.sqlite3"
        database.write_bytes(b"x" * 4096)
        with self.assertRaisesRegex(PreflightFailure, "SQLITE_INVALID_HEADER"):
            inspect_sqlite_file(database, self.base)

    def test_non_django_database_is_blocked(self):
        import sqlite3
        from scripts.production_db_readonly_preflight import PreflightFailure, inspect_sqlite_file
        database = self.base / "other.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE something (id integer)")
        with self.assertRaisesRegex(PreflightFailure, "SQLITE_DJANGO_SCHEMA_MISSING"):
            inspect_sqlite_file(database, self.base)

    def test_valid_django_database_is_read_without_sidecars_or_mutation(self):
        import sqlite3
        from scripts.production_db_readonly_preflight import inspect_sqlite_file
        database = self.base / "django.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE django_migrations (id integer)")
            connection.execute("CREATE TABLE auth_user (id integer)")
        before = database.read_bytes()
        self.assertGreaterEqual(inspect_sqlite_file(database.name, self.base), 2)
        self.assertEqual(database.read_bytes(), before)
        self.assertFalse((self.base / "django.sqlite3-wal").exists())
        self.assertFalse((self.base / "django.sqlite3-shm").exists())

    def test_symlink_is_rejected(self):
        import os
        import sqlite3
        from scripts.production_db_readonly_preflight import PreflightFailure, inspect_sqlite_file
        target = self.base / "target.sqlite3"
        with sqlite3.connect(target) as connection:
            connection.execute("CREATE TABLE django_migrations (id integer)")
            connection.execute("CREATE TABLE auth_user (id integer)")
        alias = self.base / "alias.sqlite3"
        try:
            os.symlink(target, alias)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(PreflightFailure, "SQLITE_SYMLINK"):
            inspect_sqlite_file(alias, self.base)

    def test_deploy_preflight_precedes_django_database_connection(self):
        commands = [line.strip() for line in DEPLOY.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
        safe = commands.index('"$PYTHON" scripts/production_db_readonly_preflight.py')
        check = commands.index('"$PYTHON" manage.py migrate --check')
        gate = commands.index('"$PYTHON" manage.py production_gate')
        self.assertLess(safe, check)
        self.assertLess(check, gate)

if __name__ == "__main__":
    unittest.main()
