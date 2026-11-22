#!/usr/bin/env python3
"""Verify the actual guarded installer's SQLite backup snippet off production.

Only ephemeral synthetic SQLite databases are used. No host paths or data are read.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/zomorod_business_genetics_guarded_install.sh"


def backup_code() -> str:
    content = INSTALLER.read_text(encoding="utf-8")
    pattern = r"python3 - \"\$db_file\" \"\$backup/management\.sqlite3\" <<'PY'\n(.*?)\nPY"
    scripts = re.findall(pattern, content, re.S)
    if len(scripts) != 1:
        raise AssertionError("Missing or ambiguous real SQLite backup script")
    return scripts[0]


class BackupRestoreContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zomorod-accounting-backup-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.original = self.base / "synthetic-ledger.sqlite3"
        with sqlite3.connect(self.original) as conn:
            conn.executescript("""
                CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT NOT NULL, budget INTEGER NOT NULL);
                CREATE TABLE journal_entries (id INTEGER PRIMARY KEY, doc_no TEXT NOT NULL);
                CREATE TABLE invoices (id INTEGER PRIMARY KEY, invoice_no TEXT NOT NULL);
                INSERT INTO projects(title,budget) VALUES ('SYNTHETIC-TEST', 0);
                INSERT INTO journal_entries(doc_no) VALUES ('SYNTHETIC-DOC');
                INSERT INTO invoices(invoice_no) VALUES ('SYNTHETIC-INVOICE');
            """)
        self.backup = self.base / "management.sqlite3"

    def run_backup(self, source=None, target=None):
        src = source if source is not None else self.original
        dst = target if target is not None else self.backup
        return subprocess.run(
            [sys.executable, "-c", backup_code(), str(src), str(dst)],
            capture_output=True, text=True, timeout=10, check=False,
        )

    def test_real_backup_snippet_can_restore_synthetic_accounting_rows(self):
        original_checksum = hashlib.sha256(self.original.read_bytes()).hexdigest()
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), original_checksum)
        self.assertEqual(stat.S_IMODE(self.backup.stat().st_mode), 0o600)
        restored = self.base / "restored-ledger.sqlite3"
        shutil.copy2(self.backup, restored)
        with sqlite3.connect(restored) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            for table in ("projects", "journal_entries", "invoices"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT budget FROM projects").fetchone()[0], 0)

    def test_existing_backup_is_never_overwritten(self):
        self.backup.write_bytes(b"DO_NOT_REPLACE")
        result = self.run_backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.backup.read_bytes(), b"DO_NOT_REPLACE")

    def test_dangling_symlink_backup_is_rejected(self):
        destination = self.base / "unexpected-output.sqlite3"
        self.backup.symlink_to(destination)
        result = self.run_backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.backup.is_symlink())
        self.assertFalse(destination.exists())

    def test_source_symlink_is_rejected(self):
        linked_source = self.base / "linked-source.sqlite3"
        linked_source.symlink_to(self.original)
        result = self.run_backup(source=linked_source)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
