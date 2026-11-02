"""Synthetic-only acceptance of the one-time bank chart setup CLI.

The production-only root guard is replaced only in a copied ephemeral script.
No live database, card number, or bank credential is ever read by this suite.
"""
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/zm_bank_ledger_configure_once.php"
ORIGINAL_ROOT = "/home/zomorod2/.private/zomorod-business"
REVISION = "a" * 40


class BankChartCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zm-bank-setup-")
        self.addCleanup(self.tmp.cleanup)
        self.php = shutil.which("php")
        if not self.php:
            self.skipTest("PHP CLI is required on CI")
        self.company = Path(self.tmp.name) / "company"
        self.private = self.company / ".private" / "zomorod-business"
        self.private.mkdir(parents=True)
        self.script = Path(self.tmp.name) / "configure.php"
        original = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(original.count(ORIGINAL_ROOT), 1)
        self.script.write_text(original.replace(ORIGINAL_ROOT, str(self.private)), encoding="utf-8")
        self.dbfile = self.private / "management.sqlite3"
        db = sqlite3.connect(self.dbfile)
        db.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT NOT NULL, active INTEGER NOT NULL);
        CREATE TABLE ledger_accounts (id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT,
            type TEXT, active INTEGER NOT NULL);
        CREATE TABLE journal_entries (id INTEGER PRIMARY KEY);
        CREATE TABLE journal_lines (id INTEGER PRIMARY KEY);
        CREATE TABLE invoice_payments (id INTEGER PRIMARY KEY);
        CREATE TABLE audit_events (id INTEGER PRIMARY KEY, user_id INTEGER,
            verb TEXT, subject TEXT, entity_id INTEGER);
        INSERT INTO users (id,role,active) VALUES (1,'admin',1);
        """)
        db.commit()
        db.close()
        os.chmod(self.dbfile, 0o600)

    def run_cli(self, revision=REVISION):
        return subprocess.run([self.php, str(self.script), str(self.private), revision],
                              capture_output=True, text=True, timeout=15, check=False)

    def query(self, sql):
        with sqlite3.connect(self.dbfile) as db:
            return db.execute(sql).fetchall()

    def test_01_setup_is_atomic_and_audited(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BANK_ACCOUNTS_CREATED=2", result.stdout)
        rows = self.query("SELECT code,name,type,active FROM ledger_accounts ORDER BY code")
        self.assertEqual([r[0] for r in rows], ["1011", "1012"])
        self.assertEqual([r[2:] for r in rows], [("asset", 1), ("asset", 1)])
        self.assertEqual(self.query("SELECT verb,subject FROM audit_events"),
                         [("system-configure", "bank-subledgers")])
        self.assertTrue(self.query("SELECT name FROM sqlite_master WHERE name='bank_payment_evidence'"))
        self.assertEqual(self.query("SELECT COUNT(*) FROM invoice_payments"), [(0,)])

    def test_02_consistent_prechange_backup(self):
        self.assertEqual(self.run_cli().returncode, 0)
        backup = self.company / ".backups/zm-bank-ledger-setup" / REVISION / "management.before.sqlite3"
        self.assertTrue(backup.exists())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(backup) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ledger_accounts").fetchone()[0], 0)

    def test_03_idempotent_rerun_leaves_ledgers_unchanged(self):
        self.assertEqual(self.run_cli().returncode, 0)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BANK_CHART=already_configured", result.stdout)
        self.assertEqual(self.query("SELECT COUNT(*) FROM audit_events"), [(1,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM ledger_accounts"), [(2,)])

    def test_04_partial_conflict_fails_closed(self):
        with sqlite3.connect(self.dbfile) as db:
            db.execute("INSERT INTO ledger_accounts(code,name,type,active) VALUES ('1011','unknown','asset',1)")
            db.commit()
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.query("SELECT code FROM ledger_accounts"), [("1011",)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM audit_events"), [(0,)])

    def test_05_no_active_admin_fails_without_write(self):
        with sqlite3.connect(self.dbfile) as db:
            db.execute("UPDATE users SET active=0")
            db.commit()
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM ledger_accounts"), [(0,)])

    def test_06_invalid_revision_fails_without_write(self):
        result = self.run_cli("not-a-commit")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM ledger_accounts"), [(0,)])


if __name__ == "__main__":
    unittest.main()
