"""Purely isolated regression tests for Zomorod's guarded release operations.

Does not connect to cPanel or alter a live application.
"""
import importlib.util
import os
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
                self.assertTrue(marker.stat().st_mtime_ns >= previous)

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


if __name__ == "__main__":
    unittest.main()
