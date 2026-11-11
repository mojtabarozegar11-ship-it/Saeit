"""Offline proof that the cPanel bridge never inspects a bystander Django app."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stdout, redirect_stderr
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from deploy import cpanel_public_runtime_readonly as runtime


SYNTHETIC_DB = "mysql://example:only-local-unit-test@localhost/demo"


@contextmanager
def synthetic_public_runtime():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        public = directory / "public"
        root = directory / "Saeit-staging"
        virtualenv = directory / "virtualenv" / "Saeit-staging" / "3.11" / "bin"
        public.mkdir()
        (root / "config").mkdir(parents=True)
        virtualenv.mkdir(parents=True)
        interpreter = virtualenv / "python"
        interpreter.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        interpreter.chmod(0o700)
        (public / "passenger_wsgi.py").write_text(f"APP={str(root)!r}\n", encoding="utf-8")
        (public / ".htaccess").write_text(f"PassengerPython {interpreter}\n", encoding="utf-8")
        (root / "manage.py").write_text("# synthetic\n", encoding="utf-8")
        (root / "config" / "settings.py").write_text(
            'environ.Env.read_env(BASE_DIR / ".env")\nDATABASE_URL = "test"\n', encoding="utf-8",
        )
        (root / ".env").write_text(f"DATABASE_URL={SYNTHETIC_DB}\n", encoding="utf-8")
        with patch.object(runtime, "PUBLIC_DIR", public), patch.object(runtime, "EXPECTED_ROOT", root), patch.object(
            runtime, "VENV_PREFIX", str(directory / "virtualenv") + "/"
        ):
            yield public, root, interpreter


class PublicAppRootTests(unittest.TestCase):
    def test_literal_app_assignment(self):
        self.assertEqual(runtime.declared_app_root("APP='/good/root'"), "/good/root")

    def test_dynamic_assignment_rejected(self):
        with self.assertRaises(runtime.EvidenceUnavailable):
            runtime.declared_app_root("APP=os.getenv('APP')")

    def test_multiple_assignments_rejected(self):
        with self.assertRaises(runtime.EvidenceUnavailable):
            runtime.declared_app_root("APP='/good'\nAPP='/other'")

    def test_augmented_assignment_rejected(self):
        with self.assertRaises(runtime.EvidenceUnavailable):
            runtime.declared_app_root("APP='/good'\nAPP += '/child'")

    def test_invalid_syntax_rejected(self):
        with self.assertRaises(runtime.EvidenceUnavailable):
            runtime.declared_app_root("APP=(")

    def test_unrelated_passenger_root_rejected(self):
        with synthetic_public_runtime() as (public, _, __):
            (public / "passenger_wsgi.py").write_text("APP='/home/zomorod2/Saeit'\n", encoding="utf-8")
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PUBLIC_APP_ROOT_MISMATCH"):
                runtime.verify_public_context()

    def test_missing_public_wsgi_rejected(self):
        with synthetic_public_runtime() as (public, _, __):
            (public / "passenger_wsgi.py").unlink()
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PUBLIC_PASSENGER_FILES_UNAVAILABLE"):
                runtime.verify_public_context()

    def test_missing_public_htaccess_rejected(self):
        with synthetic_public_runtime() as (public, _, __):
            (public / ".htaccess").unlink()
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PUBLIC_PASSENGER_FILES_UNAVAILABLE"):
                runtime.verify_public_context()

    def test_missing_manage_py_rejected(self):
        with synthetic_public_runtime() as (_, root, __):
            (root / "manage.py").unlink()
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PUBLIC_MANAGE_PY_MISSING"):
                runtime.verify_public_context()

    def test_missing_settings_rejected(self):
        with synthetic_public_runtime() as (_, root, __):
            (root / "config" / "settings.py").unlink()
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PUBLIC_SETTINGS_MISSING"):
                runtime.verify_public_context()

    def test_missing_dotenv_rejected(self):
        with synthetic_public_runtime() as (_, root, __):
            (root / ".env").unlink()
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PUBLIC_DOTENV_MISSING"):
                runtime.verify_public_context()

    def test_settings_without_explicit_env_loading_rejected(self):
        with synthetic_public_runtime() as (_, root, __):
            (root / "config" / "settings.py").write_text("DATABASE_URL = 'sqlite'\n", encoding="utf-8")
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PUBLIC_DATABASE_SETTINGS_UNVERIFIED"):
                runtime.verify_public_context()


class DatabaseBoundaryTests(unittest.TestCase):
    def test_mariadb_uri_accepted(self):
        runtime.non_sqlite_database_declared("DATABASE_URL=mariadb://user:pass@localhost/test")

    def test_mysql_uri_accepted(self):
        runtime.non_sqlite_database_declared("export DATABASE_URL='mysql://a:b@localhost/test'")

    def test_sqlite_fallback_rejected(self):
        with self.assertRaisesRegex(runtime.EvidenceUnavailable, "NOT_VERIFIED_MARIADB"):
            runtime.non_sqlite_database_declared("DATABASE_URL=sqlite:///db.sqlite3")

    def test_missing_db_uri_rejected(self):
        with self.assertRaisesRegex(runtime.EvidenceUnavailable, "MISSING_OR_AMBIGUOUS"):
            runtime.non_sqlite_database_declared("SECRET_KEY=local-fixture")

    def test_two_db_uri_definitions_rejected(self):
        with self.assertRaisesRegex(runtime.EvidenceUnavailable, "MISSING_OR_AMBIGUOUS"):
            runtime.non_sqlite_database_declared("DATABASE_URL=mysql://a\nDATABASE_URL=mysql://b")

    def test_invalid_db_scheme_rejected(self):
        with self.assertRaisesRegex(runtime.EvidenceUnavailable, "NOT_VERIFIED_MARIADB"):
            runtime.non_sqlite_database_declared("DATABASE_URL=postgresql://a")

    def test_public_dotenv_not_logged(self):
        with synthetic_public_runtime():
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(runtime.main(["probe", "cpanel_preflight"]), 0)
            self.assertNotIn(SYNTHETIC_DB, out.getvalue() + err.getvalue())
            self.assertIn("PUBLIC_DATABASE_QUERY=NOT_PERFORMED", out.getvalue())


class InterpreterBoundaryTests(unittest.TestCase):
    def test_missing_interpreter_directive_rejected(self):
        with synthetic_public_runtime() as (public, _, __):
            (public / ".htaccess").write_text("PassengerAppRoot /other\n", encoding="utf-8")
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PYTHON_UNVERIFIED"):
                runtime.verify_public_context()

    def test_duplicate_interpreter_directives_rejected(self):
        with synthetic_public_runtime() as (public, _, py):
            (public / ".htaccess").write_text(f"PassengerPython {py}\nPassengerPython {py}\n", encoding="utf-8")
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PYTHON_UNVERIFIED"):
                runtime.verify_public_context()

    def test_system_interpreter_rejected(self):
        with self.assertRaisesRegex(runtime.EvidenceUnavailable, "OUT_OF_SCOPE"):
            runtime.passenger_interpreter("PassengerPython /usr/bin/python3")

    def test_virtualenv_parent_traversal_rejected(self):
        with self.assertRaisesRegex(runtime.EvidenceUnavailable, "OUT_OF_SCOPE"):
            runtime.passenger_interpreter(
                "PassengerPython /home/zomorod2/virtualenv/../../../../usr/bin/python3"
            )

    def test_nonexecutable_interpreter_rejected(self):
        with synthetic_public_runtime() as (_, __, py):
            py.chmod(0o600)
            with self.assertRaisesRegex(runtime.EvidenceUnavailable, "PYTHON_MISSING"):
                runtime.verify_public_context()


class ReadonlyExecutionTests(unittest.TestCase):
    def test_direct_bridge_streams_source_owned_verifier_without_host_file_write(self):
        shell = (Path(__file__).resolve().parents[1] / "deploy" / "cpanel_direct_command.sh").read_text(encoding="utf-8")
        self.assertIn('"python3 - $operation" < deploy/cpanel_public_runtime_readonly.py', shell)
        self.assertIn('cpanel_preflight|django_check|django_migrations)', shell)
        self.assertNotIn('cd "$root"; "$python" manage.py', shell)

    def test_bridge_preserves_pinned_ssh_protection(self):
        shell = (Path(__file__).resolve().parents[1] / "deploy" / "cpanel_direct_command.sh").read_text(encoding="utf-8")
        self.assertIn('StrictHostKeyChecking yes', shell)
        self.assertIn('CPANEL_DIRECT_HOST_FINGERPRINT_MISMATCH', shell)
        self.assertIn('VPS_HOST_FINGERPRINT_MISMATCH', shell)
        self.assertNotIn('StrictHostKeyChecking no', shell)

    def test_fallback_uses_proven_cpanel_hostname_without_weakening_direct_pin(self):
        shell = (Path(__file__).resolve().parents[1] / "deploy" / "cpanel_direct_command.sh").read_text(encoding="utf-8")
        direct = shell.split('Host saeit-cpanel-direct\n', 1)[1].split('Host saeit-cpanel\n', 1)[0]
        relay = shell.split('Host saeit-cpanel\n', 1)[1].split('Host *\n', 1)[0]
        self.assertIn('HostName 178.239.147.125', direct)
        self.assertIn('ProxyJump none', direct)
        self.assertIn('HostName zohal.pws-dns.net', relay)
        self.assertIn('ProxyJump saeit-vps', relay)
        self.assertIn('ssh-keyscan -T 10 -p 1396 -t ed25519 zohal.pws-dns.net', shell)
        self.assertIn('SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04', shell)

    def test_verifier_never_executes_public_passenger_bootstrap(self):
        source = (Path(__file__).resolve().parents[1] / "deploy" / "cpanel_public_runtime_readonly.py").read_text(encoding="utf-8")
        self.assertIn('ast.parse(bootstrap)', source)
        self.assertNotIn('runpy.run_path', source)
        self.assertNotIn('exec(bootstrap', source)

    def test_unknown_operation_rejected_before_filesystem_access(self):
        err = io.StringIO()
        with redirect_stderr(err), patch.object(runtime, "verify_public_context") as verify:
            self.assertEqual(runtime.main(["probe", "delete"]), 64)
            verify.assert_not_called()

    def test_check_is_bounded_and_uses_verified_app_root(self):
        with synthetic_public_runtime() as (_, root, py):
            result = subprocess.CompletedProcess([], 0, "System check identified no issues", "")
            with patch.object(runtime.subprocess, "run", return_value=result) as run:
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(runtime.main(["probe", "django_check"]), 0)
                args, kwargs = run.call_args
                self.assertEqual(args[0], [str(py), "manage.py", "check"])
                self.assertEqual(kwargs["cwd"], str(root))
                self.assertTrue(kwargs["capture_output"])
                self.assertEqual(kwargs["timeout"], 65)
                self.assertNotIn("DATABASE_URL", kwargs["env"])
                self.assertIn("PUBLIC_DJANGO_CHECK=PASSED", output.getvalue())

    def test_migrations_report_counts_and_specific_status(self):
        with synthetic_public_runtime():
            output = "[X] contenttypes.0001_initial\n[X] core.0049_mpw_guest_email_recovery\n[ ] mpw_commerce.0004_guesttrxdelivery\n"
            with patch.object(runtime.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
                display = io.StringIO()
                with redirect_stdout(display):
                    self.assertEqual(runtime.main(["probe", "django_migrations"]), 0)
                self.assertIn("PUBLIC_MIGRATION_APPLIED_COUNT=2", display.getvalue())
                self.assertIn("PUBLIC_MIGRATION_PENDING_COUNT=1", display.getvalue())
                self.assertIn("MIGRATION_CORE_0049_MPW_GUEST_EMAIL_RECOVERY=APPLIED", display.getvalue())
                self.assertIn("MIGRATION_MPW_COMMERCE_0004_GUESTTRXDELIVERY=PENDING", display.getvalue())

    def test_absent_named_migrations_are_not_falsely_applied(self):
        with synthetic_public_runtime():
            with patch.object(runtime.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "[X] core.0001_initial\n", "")):
                display = io.StringIO()
                with redirect_stdout(display):
                    self.assertEqual(runtime.main(["probe", "django_migrations"]), 0)
                self.assertIn("NOT_PRESENT_IN_PLAN", display.getvalue())

    def test_empty_migration_plan_rejected(self):
        with synthetic_public_runtime():
            with patch.object(runtime.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "No migrations", "")):
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertEqual(runtime.main(["probe", "django_migrations"]), 2)
                self.assertIn("EMPTY_OR_UNPARSEABLE", err.getvalue())

    def test_failed_db_check_does_not_log_connection_string_or_traceback(self):
        with synthetic_public_runtime():
            failing = subprocess.CompletedProcess([], 1, "", "DATABASE_URL=private://do-not-leak")
            with patch.object(runtime.subprocess, "run", return_value=failing):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(runtime.main(["probe", "django_migrations"]), 2)
                self.assertNotIn("private://do-not-leak", out.getvalue() + err.getvalue())
                self.assertIn("PUBLIC_DJANGO_COMMAND_FAILED", err.getvalue())

    def test_timeout_rejected_without_traceback(self):
        with synthetic_public_runtime():
            with patch.object(runtime.subprocess, "run", side_effect=subprocess.TimeoutExpired(["python"], 65)):
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertEqual(runtime.main(["probe", "django_check"]), 2)
                self.assertIn("PUBLIC_DJANGO_COMMAND_UNAVAILABLE", err.getvalue())


if __name__ == "__main__":
    unittest.main()
