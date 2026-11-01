"""Purely isolated regression tests for Zomorod's guarded release operations.

Does not connect to cPanel or alter a live application.
"""
import importlib.util
import os
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("zomorod_office_guarded_release_20261031.py")
SPEC = importlib.util.spec_from_file_location("zm_guarded_release", MODULE_PATH)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class GuardedReleasePathSafetyTests(unittest.TestCase):
    def _verify_without_live_access(self, app, private):
        class FakeUser:
            pw_name = "zomorod2"

        with patch.object(release, "APP", app), patch.object(release, "PRIVATE", private), \
             patch.object(release.sys, "argv", ["release", "a" * 40]), \
             patch.object(release.pwd, "getpwuid", return_value=FakeUser()):
            return release.verify()

    def test_missing_application_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "MAIN_APPLICATION_DIRECTORY_UNSAFE"):
                self._verify_without_live_access(root / "missing-app", root / "private")

    def test_symlinked_stage_ancestor_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "app"
            app.mkdir()
            private = root / "private"
            private.mkdir()
            external = root / "external-stage"
            external.mkdir()
            (private / "zomorod-messaging-release-stages").symlink_to(
                external, target_is_directory=True
            )
            with self.assertRaisesRegex(RuntimeError, "STAGE_DIRECTORY_UNSAFE"):
                self._verify_without_live_access(app, private)

    def test_missing_staged_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "app"
            app.mkdir()
            private = root / "private"
            stage = private / "zomorod-messaging-release-stages" / ("a" * 40)
            (stage / "code").mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "STAGE_MANIFEST_OR_ARCHIVE_MISSING"):
                self._verify_without_live_access(app, private)


class GuardedReleaseRollbackTests(unittest.TestCase):
    def test_passenger_restart_creates_marker_and_updates_mtime(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            wsgi = app / "passenger_wsgi.py"
            wsgi.write_text("# validated test fixture\n")
            with patch.object(release, "APP", app), patch.object(release.time, "sleep"):
                release.restart_passenger(wsgi)
                marker = app / "tmp/restart.txt"
                self.assertTrue(marker.is_file())
                previous = marker.stat().st_mtime_ns
                with patch.object(release, "regular", wraps=release.regular):
                    release.restart_passenger(wsgi)
                self.assertGreater(marker.stat().st_mtime_ns, previous)

    def test_passenger_restart_rejects_untrusted_symlink_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            real = app / "external"
            real.mkdir()
            (app / "tmp").symlink_to(real, target_is_directory=True)
            wsgi = app / "passenger_wsgi.py"
            wsgi.write_text("# fixture")
            with patch.object(release, "APP", app):
                with self.assertRaisesRegex(RuntimeError, "PASSENGER_RESTART_DIRECTORY_UNSAFE"):
                    release.restart_passenger(wsgi)
            self.assertFalse((real / "restart.txt").exists())

    def test_atomic_copy_replaces_only_target_and_keeps_no_tempfile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private.sqlite"
            destination = root / "db.sqlite3"
            source.write_bytes(b"safe new database")
            destination.write_bytes(b"old db")
            release.atomic_copy(source, destination, 0o600)
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(source.read_bytes(), b"safe new database")
            self.assertFalse(list(root.glob(".zm-office-incoming-*")))
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_atomic_copy_failure_preserves_original_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "new"
            destination = root / "existing"
            source.write_bytes(b"updated")
            destination.write_bytes(b"original")
            with patch.object(release.os, "replace", side_effect=OSError("injected replace failure")):
                with self.assertRaises(OSError):
                    release.atomic_copy(source, destination)
            self.assertEqual(destination.read_bytes(), b"original")
            self.assertFalse(list(root.glob(".zm-office-incoming-*")))


class GuardedReleaseMfaReadinessTests(unittest.TestCase):
    """Completely in-memory SQLite fixtures, never a live corporate database."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE auth_user (
                id INTEGER PRIMARY KEY,
                is_active INTEGER NOT NULL,
                is_staff INTEGER NOT NULL,
                is_superuser INTEGER NOT NULL
            );
            CREATE TABLE otp_totp_totpdevice (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                confirmed INTEGER NOT NULL
            );
        """)

    def tearDown(self):
        self.db.close()

    def test_refuse_empty_private_office_database(self):
        with self.assertRaisesRegex(RuntimeError, "OFFICE_NAMED_ADMIN_MISSING"):
            release.require_mfa_provisioned(self.db)

    def test_refuse_administrator_without_confirmed_second_factor(self):
        self.db.execute(
            "INSERT INTO auth_user(id,is_active,is_staff,is_superuser) VALUES (1,1,1,1)"
        )
        self.db.execute(
            "INSERT INTO otp_totp_totpdevice(id,user_id,confirmed) VALUES (1,1,0)"
        )
        with self.assertRaisesRegex(RuntimeError, "OFFICE_ADMIN_MFA_DEVICE_MISSING"):
            release.require_mfa_provisioned(self.db)

    def test_accept_only_confirmed_device_for_active_superuser(self):
        self.db.execute(
            "INSERT INTO auth_user(id,is_active,is_staff,is_superuser) VALUES (1,1,1,1)"
        )
        self.db.execute(
            "INSERT INTO otp_totp_totpdevice(id,user_id,confirmed) VALUES (1,1,1)"
        )
        release.require_mfa_provisioned(self.db)

    def test_missing_totp_schema_fails_closed(self):
        self.db.execute("DROP TABLE otp_totp_totpdevice")
        with self.assertRaisesRegex(RuntimeError, "OFFICE_MFA_SCHEMA_NOT_READY"):
            release.require_mfa_provisioned(self.db)


class GuardedReleaseDependencyPreflightTests(unittest.TestCase):
    """No real interpreter or live files are touched by these mocks."""

    def test_missing_passenger_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(release, "HOME", Path(directory)):
                with self.assertRaisesRegex(RuntimeError, "PASSENGER_PYTHON_UNATTESTED"):
                    release.production_python()

    def test_uses_public_document_root_not_app_local_htaccess(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "Saeit"
            app.mkdir()
            configured = root / "virtualenv/Saeit/bin/python"
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"fixture")
            configured.chmod(0o755)
            public_html = root / "public_html"
            public_html.mkdir()
            (public_html / ".htaccess").write_text(
                '# cPanel config\nPassengerAppRoot "' + str(app) + '"\nPassengerPython "' + str(configured) + '"\n',
                encoding="utf-8",
            )
            (app / ".htaccess").write_text("PassengerPython /nonexistent\n")
            with patch.object(release, "HOME", root), patch.object(release, "APP", app):
                selected = release.production_python()
            self.assertEqual(selected, configured)

    def test_app_local_htaccess_alone_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".htaccess").write_text("PassengerPython /opt/python\n")
            with patch.object(release, "HOME", root), patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "PASSENGER_PYTHON_UNATTESTED"):
                    release.production_python()

    def test_wrong_passenger_app_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "Saeit"
            public_html = root / "public_html"
            public_html.mkdir()
            configured = root / "bin/python"
            configured.parent.mkdir()
            configured.write_bytes(b"fixture")
            configured.chmod(0o755)
            (public_html / ".htaccess").write_text(
                'PassengerAppRoot "/another-app"\nPassengerPython "' + str(configured) + '"\n',
                encoding="utf-8",
            )
            with patch.object(release, "HOME", root), patch.object(release, "APP", app):
                with self.assertRaisesRegex(RuntimeError, "PASSENGER_APP_ROOT_UNATTESTED"):
                    release.production_python()

    def test_duplicate_passenger_interpreters_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public_html = root / "public_html"
            public_html.mkdir()
            (public_html / ".htaccess").write_text(
                "PassengerPython /opt/python3\nPassengerPython /opt/python4\n",
                encoding="utf-8",
            )
            with patch.object(release, "HOME", root):
                with self.assertRaisesRegex(RuntimeError, "PASSENGER_PYTHON_UNATTESTED"):
                    release.production_python()

    def test_preflight_uses_isolated_python_and_pinned_otp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            interpreter = root / "bin/python"
            with patch.object(release, "APP", root), patch.object(
                release.subprocess, "run", return_value=release.subprocess.CompletedProcess([], 0)
            ) as runner:
                release.require_production_dependencies(interpreter)
            args, kwargs = runner.call_args
            self.assertEqual(args[0][:4], [str(interpreter), "-I", "-B", "-c"])
            self.assertIn("django_otp", args[0][4])
            self.assertIn("1.7.5", args[0][4])
            self.assertEqual(kwargs["cwd"], root)
            self.assertEqual(kwargs["capture_output"], True)
            self.assertEqual(kwargs["check"], False)

    def test_preflight_rejects_missing_or_mismatched_otp(self):
        with patch.object(
            release.subprocess, "run", return_value=release.subprocess.CompletedProcess([], 1)
        ):
            with self.assertRaisesRegex(RuntimeError, "PRODUCTION_DEPENDENCY_PREFLIGHT_FAILED"):
                release.require_production_dependencies(Path("/nonexistent/virtualenv/bin/python"))

    def test_preflight_timeout_fails_closed(self):
        with patch.object(
            release.subprocess, "run", side_effect=release.subprocess.TimeoutExpired("python", 25)
        ):
            with self.assertRaisesRegex(RuntimeError, "PRODUCTION_DEPENDENCY_PREFLIGHT_FAILED"):
                release.require_production_dependencies(Path("/nonexistent/virtualenv/bin/python"))


if __name__ == "__main__":
    unittest.main()
