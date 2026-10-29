#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import erp_offline_gate as gate

class OfflineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="zomorod-erp-offline-")
        self.file=Path(self.temp.name)/'test.sqlite3'
        with sqlite3.connect(self.file) as db:
            db.executescript('''
                CREATE TABLE users(id INTEGER PRIMARY KEY);
                CREATE TABLE ledger_accounts(id INTEGER PRIMARY KEY);
                CREATE TABLE journal_entries(id INTEGER PRIMARY KEY);
                CREATE TABLE journal_lines(id INTEGER PRIMARY KEY,entry_id INTEGER REFERENCES journal_entries(id),currency TEXT,debit INTEGER,credit INTEGER);
                CREATE TABLE invoices(id INTEGER PRIMARY KEY, amount INTEGER);
                CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY,invoice_id INTEGER REFERENCES invoices(id), amount INTEGER);
                CREATE TABLE inventory(id INTEGER PRIMARY KEY);
                CREATE TABLE inventory_movements(id INTEGER PRIMARY KEY,inventory_id INTEGER REFERENCES inventory(id), qty INTEGER);
                INSERT INTO journal_entries VALUES(1);
                INSERT INTO journal_lines VALUES(1,1,'IRR',1000,0),(2,1,'IRR',0,1000);
                INSERT INTO invoices VALUES(1,1000);
                INSERT INTO invoice_payments VALUES(1,1,500);
                INSERT INTO inventory VALUES(1);
                INSERT INTO inventory_movements VALUES(1,1,5);
            ''')
        self.original=self.file.read_bytes()

    def tearDown(self):self.temp.cleanup()
    def test_clean_snapshot_and_restoration(self):
        self.assertEqual(gate.inspect(self.file, gate.FINANCE_TABLES)["result"],"PASS_CHECKED_INVARIANTS")
        self.assertEqual(gate.verified_restore(self.file,gate.FINANCE_TABLES)["result"],"PASS_CHECKED_INVARIANTS")
        self.assertEqual(self.original,self.file.read_bytes())
    def test_imbalanced_journal_overpayment_negative_stock_detected(self):
        with sqlite3.connect(self.file) as db:
            db.executescript('''
                INSERT INTO journal_entries VALUES(2);
                INSERT INTO journal_lines VALUES(3,2,'USD',900,0),(4,2,'USD',0,300);
                INSERT INTO invoice_payments VALUES(2,1,700);
                INSERT INTO inventory_movements VALUES(2,1,-10);
            ''')
        result=gate.inspect(self.file, gate.FINANCE_TABLES)
        self.assertEqual(result['result'],"INCOMPLETE_OR_NEEDS_INVESTIGATION")
        self.assertEqual(result['anomalies']['currency_unbalanced_entries'],1)
        self.assertEqual(result['anomalies']['overpaid_invoices'],1)
        self.assertEqual(result['anomalies']['negative_stock'],1)
    def test_missing_table_not_success(self):
        with sqlite3.connect(self.file) as db:db.execute('DROP TABLE ledger_accounts')
        data=gate.inspect(self.file,gate.FINANCE_TABLES)
        self.assertIn('ledger_accounts',data['missing_tables'])
        self.assertNotEqual(data['result'],"PASS_CHECKED_INVARIANTS")
    def test_missing_database_never_created(self):
        p=Path(self.temp.name)/'does-not-exist.sqlite3'
        with self.assertRaises(ValueError):gate.inspect(p,gate.FINANCE_TABLES)
        self.assertFalse(p.exists())
    def test_wrong_control_domain_fails_closed(self):
        self.assertEqual(gate.inspect(self.file,gate.CONTROL_TABLES)['result'],"INCOMPLETE_OR_NEEDS_INVESTIGATION")
    def test_cli_exit_and_no_side_effects(self):
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('erp_offline_gate.py')),
                             str(self.file),'--restore-test'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertTrue(json.loads(proc.stdout)['restore_test'])
        self.assertEqual(self.file.read_bytes(),self.original)
    def test_symlink_refused(self):
        linked=Path(self.temp.name)/'symlink.sqlite3'
        linked.symlink_to(self.file)
        with self.assertRaises(ValueError):gate.inspect(linked,gate.FINANCE_TABLES)
    def test_foreign_key_violation_detected(self):
        with sqlite3.connect(self.file) as db:db.execute("INSERT INTO journal_lines VALUES(6,999,'IRR',10,0)")
        out=gate.inspect(self.file,gate.FINANCE_TABLES)
        self.assertGreater(out['foreign_key_violations'],0)

if __name__=='__main__':unittest.main(verbosity=2)
