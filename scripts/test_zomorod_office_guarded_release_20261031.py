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


if __name__ == "__main__":
    unittest.main()
