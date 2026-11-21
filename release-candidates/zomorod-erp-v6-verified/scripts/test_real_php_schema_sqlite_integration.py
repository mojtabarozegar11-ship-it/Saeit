#!/usr/bin/env python3
"""SQLite-only reconstruction of real PHP schema DDL; no production operations.

It extracts SQL DDL from checked-in PHP rather than duplicating schema fixtures.
It is NOT a PHP runtime functional test.
"""
from __future__ import annotations
import importlib.util
import pathlib
import re
import sqlite3
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parent.parent
APP=(ROOT/'content/zomorod-business/app.php').read_text()
PERIOD=(ROOT/'content/zomorod-business/period_controls.php').read_text()
CREATE_TABLES=re.findall(r'\$db->exec\("(CREATE TABLE.*?)(?<!\\)"\);',APP,re.S)
PERIOD_DDL=re.findall(r'\$db->exec\("(CREATE (?:TABLE|TRIGGER|INDEX).*?)(?<!\\)"\);',PERIOD,re.S)
spec=importlib.util.spec_from_file_location('real_finance',ROOT/'scripts/finance_invariants.py')
finance=importlib.util.module_from_spec(spec)
spec.loader.exec_module(finance)

class RealSchemaIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='zm-real-php-schema-')
        self.path=pathlib.Path(self.tmp.name)/'synthetic.sqlite3'
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA foreign_keys=ON')
        for ddl in CREATE_TABLES+PERIOD_DDL:
            self.db.execute(ddl)
        self.db.execute("INSERT INTO users(id,username,password_hash,role) VALUES(1,'syntheticA','x','admin'),(2,'syntheticB','y','admin')")
        for idx,code,kind in ((1,'1010','asset'),(2,'1100','asset'),(3,'1200','asset'),(4,'2000','liability'),(5,'4000','income')):
            self.db.execute('INSERT INTO ledger_accounts(id,code,name,type) VALUES(?,?,?,?)',(idx,code,'synthetic',kind))
        self.db.execute("INSERT INTO parties(id,name,kind) VALUES(1,'Synthetic Customer','customer')")
        self.db.commit()

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def journal(self,id,date,debit,credit,amount,currency='IRR'):
        self.db.execute('INSERT INTO journal_entries(id,doc_no,doc_date,note,entered_by) VALUES(?,?,?,?,1)',(id,f'SYN-{id}',date,'Synthetic journal'))
        self.db.execute('INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)',(id,debit,amount,0,currency))
        self.db.execute('INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)',(id,credit,0,amount,currency))

    def initial_invoice(self):
        self.journal(1,'2026-10-15',2,5,10000)
        self.db.execute("INSERT INTO invoices(invoice_no,kind,party_id,invoice_date,due_date,description,amount,currency,posted_entry,created_by) VALUES('SYN-INV-1','sale',1,'2026-10-15','2026-11-15','synthetic',10000,'IRR',1,1)")

    def test_reconstructed_php_schema_all_tables_and_triggers(self):
        self.assertEqual(len(CREATE_TABLES),13)
        table_names={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue(set(finance.TABLES).issubset(table_names))
        self.assertIn('zm_accounting_periods',table_names)
        self.assertGreaterEqual(self.db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0],20)
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_synthetic_invoice_payment_and_read_only_finance_audit(self):
        self.initial_invoice()
        self.journal(2,'2026-11-16',1,2,3000)
        self.db.execute("INSERT INTO invoice_payments(invoice_id,amount,paid_on,entry_id,created_by) VALUES(1,3000,'2026-11-16',2,1)")
        self.db.commit()
        self.assertEqual(finance.audit(self.path)['status'],'PASS_CHECKED_INVARIANTS')

    def test_existing_posting_cannot_be_reused(self):
        self.initial_invoice()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO invoices(invoice_no,kind,party_id,invoice_date,due_date,description,amount,currency,posted_entry,created_by) VALUES('SYN-INV-2','sale',1,'2026-10-15','2026-11-15','dup',10000,'IRR',1,1)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO invoice_payments(invoice_id,amount,paid_on,entry_id,created_by) VALUES(1,3000,'2026-11-16',1,1)")

    def test_closed_period_blocks_legacy_sql_and_allows_open_month_payment(self):
        self.initial_invoice()
        self.db.execute("INSERT INTO zm_accounting_periods(period_key,state,requested_by,snapshot_sha256,request_note) VALUES('2026-10','pending',1,?, 'synthetic')",('a'*64,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.journal(3,'2026-10-16',2,5,500)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE invoices SET description='hacked' WHERE id=1")
        self.journal(4,'2026-11-16',1,2,3000)
        self.db.execute("INSERT INTO invoice_payments(invoice_id,amount,paid_on,entry_id,created_by) VALUES(1,3000,'2026-11-16',4,1)")
        self.db.execute("UPDATE zm_accounting_periods SET state='closed',approved_by=2,decision_note='reviewed' WHERE period_key='2026-10'")
        self.db.commit()
        self.assertEqual(finance.audit(self.path)['status'],'PASS_CHECKED_INVARIANTS')

    def test_frozen_period_financial_line_update_rejected(self):
        self.initial_invoice()
        self.db.execute("INSERT INTO zm_accounting_periods(period_key,state,requested_by,snapshot_sha256,request_note) VALUES('2026-10','pending',1,?,'synthetic')",('a'*64,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('UPDATE journal_lines SET debit=9999 WHERE entry_id=1 AND debit>0')

if __name__=='__main__':unittest.main(verbosity=2)
