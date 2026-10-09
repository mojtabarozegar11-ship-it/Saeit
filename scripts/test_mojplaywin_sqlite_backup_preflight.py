"""Unit tests for the offline MojPlayWin SQLite backup preflight."""
import contextlib
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import mojplaywin_sqlite_backup_preflight as backup


class SQLiteBackupPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "active.sqlite3"
        self.out = self.root / "private"
        self.out.mkdir(mode=0o700)
        self.public = self.root / "public_html"
        self.public.mkdir()
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO demo(value) VALUES ('preserved')")
        self.fake_django = types.ModuleType("django")
        self.fake_django.setup = lambda: None
        self.fake_db = types.ModuleType("django.db")
        self.fake_db.connections = {"default": types.SimpleNamespace(settings_dict={
            "ENGINE": "django.db.backends.sqlite3", "NAME": str(self.db)
        })}

    def run_preflight(self, out=None):
        argv = ["preflight", "--output-dir", str(out or self.out),
                "--web-root", str(self.public)]
        with patch.dict(sys.modules, {"django": self.fake_django, "django.db": self.fake_db}):
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()) as output:
                backup.main()
        return output.getvalue()

    def test_consistent_backup_preserves_rows(self):
        result = self.run_preflight()
        self.assertIn("BACKUP_INTEGRITY=ok", result)
        backups = list(self.out.glob("mojplaywin-db-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as conn:
            self.assertEqual(conn.execute("SELECT value FROM demo").fetchone()[0], "preserved")

    def test_rejects_backup_in_web_root(self):
        web_backup = self.public / "backups"
        web_backup.mkdir(mode=0o700)
        with self.assertRaisesRegex(SystemExit, "served web root"):
            self.run_preflight(web_backup)
        self.assertEqual(list(web_backup.iterdir()), [])

    def test_rejects_non_private_backup_directory(self):
        os.chmod(self.out, 0o755)
        with self.assertRaisesRegex(SystemExit, "0700"):
            self.run_preflight()
        self.assertEqual(list(self.out.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
