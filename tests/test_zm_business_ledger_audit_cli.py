#!/usr/bin/env python3
"""Isolated, nonproduction accounting audit acceptance tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "content/zomorod-business"


class LedgerAuditCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="zm-audit-isolated-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        program = self.root / "content/zomorod-business/app.php"
        program.parent.mkdir(parents=True)
        shutil.copy2(SOURCE / "app.php", program)
        self.private = self.root / ".private/zomorod-business"
        self.private.mkdir(parents=True)
        self.script = self.private / "tools/ledger_audit_cli.php"
        self.script.parent.mkdir(mode=0o700)
        shutil.copy2(SOURCE / "ledger_audit_cli.php", self.script)
        self.script.chmod(0o600)
        init = subprocess.run(["php", str(program), "--initialize-private-db"],
                              capture_output=True, text=True, timeout=12)
        self.assertEqual(init.returncode, 0, init.stderr[-200:])
        self.database = self.private / "management.sqlite3"

    def audit(self) -> tuple[int, dict]:
        result = subprocess.run(["php", str(self.script)], capture_output=True,
                                text=True, timeout=12)
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn(".private/", result.stdout)
        return result.returncode, json.loads(result.stdout)

    def create_admin(self) -> int:
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO users(username,password_hash,role,active) VALUES(?,?,?,1)",
                       ("qa_only", "synthetic-do-not-login", "admin"))
            return db.execute("SELECT last_insert_rowid()").fetchone()[0]

    def add_journal(self, user: int, name: str, balance: bool = True) -> int:
        with sqlite3.connect(self.database) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("INSERT INTO journal_entries(doc_no,doc_date,note,entered_by) VALUES(?,?,?,?)",
                       (name, "2026-11-02", "synthetic-only", user))
            journal = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            ids = [row[0] for row in db.execute(
                "SELECT id FROM ledger_accounts WHERE code IN ('1000','4000') ORDER BY code")]
            db.execute("INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)",
                       (journal, ids[0], 12000, 0, "IRR"))
            db.execute("INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)",
                       (journal, ids[1], 0, 12000 if balance else 11900, "IRR"))
        return journal

    def test_empty_but_initialized_book_requires_active_admin(self) -> None:
        code, report = self.audit()
        self.assertEqual(code, 2)
        self.assertEqual(report["result"], "REVIEW_REQUIRED")
        self.assertFalse(report["checks"]["active_administrator"])
        self.assertTrue(report["checks"]["sqlite_integrity"])
        self.assertEqual(report["external_bank_reconciliation"], "NOT_PROVEN")

    def test_balanced_book_passes_and_durable_files_do_not_change(self) -> None:
        user = self.create_admin()
        self.add_journal(user, "QA-JOURNAL", balance=True)

        def files() -> dict[str, str]:
            return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.private.glob("management.sqlite3*")
                    if p.is_file() and p.name != "management.sqlite3-shm"}

        before = files()
        code, report = self.audit()
        self.assertEqual(code, 0)
        self.assertEqual(report["result"], "PASS")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(files(), before)

    def test_unbalanced_entry_is_detected_without_customer_details(self) -> None:
        user = self.create_admin()
        self.add_journal(user, "QA-SECRET-CUSTOMER", balance=False)
        code, report = self.audit()
        self.assertEqual(code, 2)
        self.assertFalse(report["checks"]["balanced_journals_per_currency"])
        self.assertNotIn("QA-SECRET-CUSTOMER", json.dumps(report))
        self.assertTrue(report["checks"]["foreign_keys"])

    def test_overpaid_invoice_is_detected(self) -> None:
        user = self.create_admin()
        invoice_journal = self.add_journal(user, "QA-INVOICE")
        payment_journal = self.add_journal(user, "QA-PAYMENT")
        with sqlite3.connect(self.database) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("INSERT INTO parties(name,kind) VALUES(?,?)", ("PRIVATE-BUYER", "both"))
            party = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("""INSERT INTO invoices(invoice_no,kind,party_id,invoice_date,due_date,
                description,amount,currency,posted_entry,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                ("INV-TEST", "sale", party, "2026-11-02", "2026-12-01", "test", 10000, "IRR", invoice_journal, user))
            invoice = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO invoice_payments(invoice_id,amount,paid_on,entry_id,created_by) VALUES(?,?,?,?,?)",
                       (invoice, 10001, "2026-11-02", payment_journal, user))
        code, report = self.audit()
        self.assertEqual(code, 2)
        self.assertFalse(report["checks"]["no_invoice_overpayments"])
        self.assertTrue(report["checks"]["balanced_journals_per_currency"])
        self.assertNotIn("PRIVATE-BUYER", json.dumps(report))

    def test_missing_database_does_not_get_recreated(self) -> None:
        hidden = self.private / "management.hidden.sqlite3"
        self.database.rename(hidden)
        try:
            code, report = self.audit()
            self.assertEqual(code, 2)
            self.assertFalse(report["checks"]["private_database"])
            self.assertFalse(self.database.exists())
        finally:
            hidden.rename(self.database)


if __name__ == "__main__":
    unittest.main()
