#!/usr/bin/env python3
"""Synthetic independent posting consistency, rollback and read-only audit checks."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from finance_invariants import audit


class FinanceInvariants(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='zm-finance-audit-')
        self.path=Path(self.temp.name)/'synthetic.sqlite3'
        with sqlite3.connect(self.path) as db:
            db.executescript('''
                PRAGMA foreign_keys=ON;
                CREATE TABLE ledger_accounts(id INTEGER PRIMARY KEY,code TEXT UNIQUE);
                INSERT INTO ledger_accounts VALUES (1,'1010'),(2,'1100'),(3,'1200'),(4,'2000'),(5,'4000');
                CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_date TEXT);
                CREATE TABLE journal_lines(id INTEGER PRIMARY KEY,entry_id INTEGER REFERENCES journal_entries(id),
                   account_id INTEGER REFERENCES ledger_accounts(id),currency TEXT,debit INTEGER,credit INTEGER);
                CREATE TABLE invoices(id INTEGER PRIMARY KEY,kind TEXT,invoice_date TEXT,
                   amount INTEGER,currency TEXT,posted_entry INTEGER REFERENCES journal_entries(id));
                CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY,invoice_id INTEGER REFERENCES invoices(id),
                   amount INTEGER,paid_on TEXT,entry_id INTEGER REFERENCES journal_entries(id));
                CREATE TABLE inventory(id INTEGER PRIMARY KEY);
                CREATE TABLE inventory_movements(id INTEGER PRIMARY KEY,inventory_id INTEGER REFERENCES inventory(id),qty INTEGER);
                INSERT INTO journal_entries VALUES(1,'2026-10-20'),(2,'2026-10-21');
                INSERT INTO journal_lines VALUES(1,1,2,'IRR',10000,0),(2,1,5,'IRR',0,10000),
                     (3,2,1,'IRR',3000,0),(4,2,2,'IRR',0,3000);
                INSERT INTO invoices VALUES(1,'sale','2026-10-20',10000,'IRR',1);
                INSERT INTO invoice_payments VALUES(1,1,3000,'2026-10-21',2);
                INSERT INTO inventory VALUES(1);
                INSERT INTO inventory_movements VALUES(1,1,5);
            ''')
        os.chmod(self.path,0o600)

    def tearDown(self):self.temp.cleanup()
    def change(self,statement):
        with sqlite3.connect(self.path) as db:db.executescript(statement)
    def case(self,expected):
        d=audit(self.path)
        self.assertEqual(d['issues'][expected],1,d)
        self.assertEqual(d['status'],'FAIL_REQUIRES_INVESTIGATION')

    def test_clean_template_and_read_only(self):
        before=self.path.read_bytes()
        d=audit(self.path)
        self.assertEqual(d['status'],'PASS_CHECKED_INVARIANTS')
        self.assertTrue(d['readonly'])
        self.assertEqual(before,self.path.read_bytes(),'read-only audit altered SQLite')

    def test_wrong_invoice_account_even_when_balanced(self):
        self.change("UPDATE journal_lines SET account_id=1 WHERE id=1;")
        self.case('invoice_posting_mismatch')

    def test_wrong_payment_account_even_when_balanced(self):
        self.change("UPDATE journal_lines SET account_id=3 WHERE id=4;")
        self.case('payment_posting_mismatch')

    def test_tampered_amount_and_overpayment(self):
        self.change("UPDATE invoice_payments SET amount=14000 WHERE id=1;")
        self.case('overpaid_invoices')

    def test_wrong_currency_dates(self):
        self.change("UPDATE journal_lines SET currency='EUR' WHERE id=4;")
        self.case('payment_posting_mismatch')

    def test_negative_stock(self):
        self.change("UPDATE inventory_movements SET qty=-3 WHERE id=1;")
        self.case('negative_stock')

    def test_reused_posting_among_two_invoices(self):
        self.change("INSERT INTO invoices VALUES(2,'sale','2026-10-20',10000,'IRR',1);")
        self.case('posting_reuse')

    def test_cross_family_reused_posting(self):
        # Reusing an invoice posting as payment must be visible even when its
        # account/currency template was altered to make both appear balanced.
        self.change("UPDATE invoice_payments SET entry_id=1 WHERE id=1;")
        self.case('posting_reuse')

    def test_historical_negative_stock_with_positive_final_balance(self):
        # The inventory ends positive but was negative after its first movement.
        self.change("UPDATE inventory_movements SET qty=-5 WHERE id=1;"
                    "INSERT INTO inventory_movements VALUES(2,1,15);")
        result=audit(self.path)
        self.assertEqual(result['issues']['negative_stock'],0)
        self.assertEqual(result['issues']['historical_negative_stock'],1)
        self.assertEqual(result['status'],'FAIL_REQUIRES_INVESTIGATION')

    def test_unbalanced_journal(self):
        self.change("UPDATE journal_lines SET credit=2600 WHERE id=4;")
        self.case('unbalanced_entries')

    def test_missing_line(self):
        self.change("DELETE FROM journal_lines WHERE id=4;")
        self.case('too_few_lines')

    def test_missing_db_does_not_create_one(self):
        missing=Path(self.temp.name)/'missing.sqlite3'
        with self.assertRaises(ValueError):audit(missing)
        self.assertFalse(missing.exists())

    def test_schema_missing_fails_closed(self):
        self.change('DROP TABLE invoice_payments;')
        with self.assertRaises(ValueError):audit(self.path)


if __name__=='__main__':unittest.main(verbosity=2)
