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



class GuardedStageArchiveIntegrityTests(unittest.TestCase):
    """Synthetic local archive fixtures; no SSH, cPanel or production DB."""

    def make_stage(self, root):
        import io
        import tarfile
        stage = Path(root)
        code = stage / "code"
        files = {
            "company_messaging/models.py": b"class Example: pass\\n",
            "config/settings.py": b"DEBUG = False\\n",
        }
        with tarfile.open(stage / "package.tar", "w") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
                target = code / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        return stage, code

    def test_exact_archive_and_extracted_files_pass(self):
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            self.assertEqual(release.require_stage_payload_matches_archive(stage, code), 2)

    def test_modified_extracted_settings_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            (code / "config/settings.py").write_text("DEBUG = True")
            with self.assertRaisesRegex(RuntimeError, "STAGE_EXTRACTED_FILE_CHANGED"):
                release.require_stage_payload_matches_archive(stage, code)

    def test_extra_unarchived_python_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            (code / "config/extra.py").write_text("raise RuntimeError('extra')")
            with self.assertRaisesRegex(RuntimeError, "STAGE_EXTRACTED_EXECUTABLE_UNARCHIVED"):
                release.require_stage_payload_matches_archive(stage, code)

    def test_extracted_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            target = code / "config/settings.py"
            target.unlink()
            target.symlink_to(code / "company_messaging/models.py")
            with self.assertRaisesRegex(RuntimeError, "STAGE_EXTRACTED_SYMLINK"):
                release.require_stage_payload_matches_archive(stage, code)


    def test_archive_backslash_name_fails_closed(self):
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            with tarfile.open(stage / "package.tar", "a") as tar:
                data = b"bad"
                info = tarfile.TarInfo("config\\extra.py")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            with self.assertRaisesRegex(RuntimeError, "STAGE_ARCHIVE_PATH_UNSAFE"):
                release.require_stage_payload_matches_archive(stage, code)

    def test_archive_path_traversal_fails_closed(self):
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            with tarfile.open(stage / "package.tar", "a") as tar:
                data = b"bad"
                info = tarfile.TarInfo("../escape.py")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            with self.assertRaisesRegex(RuntimeError, "STAGE_ARCHIVE_PATH_UNSAFE"):
                release.require_stage_payload_matches_archive(stage, code)



    def test_extra_unarchived_template_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            extra = code / "company_messaging/templates/unsafe.html"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("<script>unexpected()</script>")
            with self.assertRaisesRegex(RuntimeError, "STAGE_EXTRACTED_ASSET_UNARCHIVED"):
                release.require_stage_payload_matches_archive(stage, code)

    def test_extra_unarchived_javascript_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            stage, code = self.make_stage(d)
            extra = code / "company_messaging/static/unsafe.js"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("console.log('unarchived')")
            with self.assertRaisesRegex(RuntimeError, "STAGE_EXTRACTED_ASSET_UNARCHIVED"):
                release.require_stage_payload_matches_archive(stage, code)

    def test_stage_parent_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root / "real"
            real.mkdir()
            stage, code = self.make_stage(real)
            alias = root / "alias"
            alias.symlink_to(stage, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "STAGE_ANCESTOR_SYMLINK"):
                release.require_stage_payload_matches_archive(alias, alias / "code")

    def test_release_verify_is_not_disabled_by_python_optimized_mode(self):
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(release.verify))
        self.assertFalse(any(isinstance(n, ast.Assert) for n in ast.walk(tree)))

if __name__ == "__main__":
    unittest.main()
