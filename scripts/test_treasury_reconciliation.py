#!/usr/bin/env python3
"""Deterministic treasury checks on disposable SQLite and synthetic statements."""
from __future__ import annotations
import datetime as dt
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from treasury_reconciliation import (InputRejected, aging, bank_ledger, iso_date,
    open_readonly, parse_statement, reconcile, run)


class TreasuryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='zm-treasury-synthetic-')
        self.root=Path(self.temp.name)
        self.db=self.root/'finance.sqlite3'
        with sqlite3.connect(self.db) as conn:
            conn.execute('PRAGMA foreign_keys=ON')
            conn.executescript('''
              CREATE TABLE ledger_accounts(id INTEGER PRIMARY KEY,code TEXT UNIQUE,type TEXT,active INTEGER);
              CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_no TEXT UNIQUE,doc_date TEXT);
              CREATE TABLE journal_lines(id INTEGER PRIMARY KEY,entry_id INTEGER REFERENCES journal_entries(id),account_id INTEGER REFERENCES ledger_accounts(id),debit INTEGER,credit INTEGER,currency TEXT);
              CREATE TABLE invoices(id INTEGER PRIMARY KEY,kind TEXT,invoice_date TEXT,due_date TEXT,amount INTEGER,currency TEXT);
              CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY,invoice_id INTEGER REFERENCES invoices(id),amount INTEGER,paid_on TEXT);
              INSERT INTO ledger_accounts VALUES(1,'1010','asset',1),(2,'1100','asset',1),(3,'2000','liability',1);
              INSERT INTO journal_entries VALUES(1,'PAY-01','2026-10-20'),(2,'PAY-02','2026-10-21');
              INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES
              (1,1,2500,0,'IRR'),(1,2,0,2500,'IRR'),
              (2,3,800,0,'IRR'),(2,1,0,800,'IRR');
              INSERT INTO invoices VALUES
              (1,'sale','2026-10-10','2026-10-15',10000,'IRR'),
              (2,'purchase','2026-09-01','2026-09-01',5000,'IRR');
              INSERT INTO invoice_payments VALUES(1,1,2500,'2026-10-20'),(2,2,800,'2026-10-21');
            ''')
        self.statement=self.root/'statement.csv'
        self.statement.write_bytes(b'reference,date,currency,amount_minor\nPAY-01,2026-10-20,IRR,2500\nPAY-02,2026-10-22,IRR,-800\n')
        self.hash=hashlib.sha256(self.db.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def read_db(self):return open_readonly(self.db)

    def test_balanced_signed_bank_reconciliation(self):
        self.assertEqual(run(self.db,self.statement,'2026-10-30')['reconciliation']['status'],'BALANCED_MATCHED')
    def test_never_changes_db_bytes(self):
        run(self.db,self.statement,'2026-10-30')
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(),self.hash)
    def test_exact_currency_totals(self):
        report=run(self.db,self.statement,'2026-10-30')['reconciliation']
        self.assertEqual(report['currency_totals']['IRR']['statement_net_minor'],1700)
        self.assertEqual(report['currency_totals']['IRR']['ledger_net_minor'],1700)
        self.assertEqual(report['matched_count'],2)
    def test_receivables_and_payables_aging(self):
        result=run(self.db,self.statement,'2026-10-30')['aging']['receivables_payables_minor']
        self.assertEqual(result['sale']['IRR']['days_1_30'],7500)
        self.assertEqual(result['purchase']['IRR']['days_31_60'],4200)
    def test_future_payments_not_counted(self):
        with sqlite3.connect(self.db) as conn:conn.execute("UPDATE invoice_payments SET paid_on='2026-11-01' WHERE id=1")
        with self.read_db() as conn:self.assertEqual(aging(conn,dt.date(2026,10,30))['receivables_payables_minor']['sale']['IRR']['total'],10000)
    def test_mismatch_even_if_totals_balance(self):
        b=b'reference,date,currency,amount_minor\nPAY-01,2026-10-20,IRR,2400\nPAY-02,2026-10-21,IRR,-700\n'
        with self.read_db() as conn:
            r=reconcile(conn,parse_statement(b))
        self.assertEqual(r['mismatch_count'],2)
        self.assertEqual(r['currency_totals']['IRR']['unreconciled_difference_minor'],0)
        self.assertEqual(r['status'],'REVIEW_REQUIRED')
    def test_missing_statement_entry(self):
        with self.read_db() as conn:r=reconcile(conn,parse_statement(b'reference,date,currency,amount_minor\nPAY-01,2026-10-20,IRR,2500\n'))
        self.assertEqual(r['ledger_only_count'],1)
    def test_unmatched_bank_statement(self):
        with self.read_db() as conn:r=reconcile(conn,parse_statement(b'reference,date,currency,amount_minor\nUNKNOWN,2026-10-20,IRR,2500\n'))
        self.assertEqual(r['statement_only_count'],1)
        self.assertEqual(r['ledger_only_count'],2)
    def test_large_date_lag_flagged(self):
        with self.read_db() as conn:r=reconcile(conn,parse_statement(b'reference,date,currency,amount_minor\nPAY-01,2026-11-15,IRR,2500\n'))
        self.assertEqual(r['mismatch_count'],1)
    def test_lag_override(self):
        with self.read_db() as conn:
            r=reconcile(conn,parse_statement(b'reference,date,currency,amount_minor\nPAY-01,2026-11-15,IRR,2500\n'),max_date_lag=30)
        self.assertEqual(r['matched_count'],1)
    def test_duplicate_reference_rejected(self):
        with self.assertRaises(InputRejected):parse_statement(b'reference,date,currency,amount_minor\nPAY-01,2026-10-20,IRR,2500\nPAY-01,2026-10-20,IRR,2500\n')
    def test_negative_zero_invalid_and_tampered_numbers(self):
        for amount in ('0','-0','25.00','+20','1e6','01'):
            with self.subTest(amount=amount),self.assertRaises(InputRejected):
                parse_statement(('reference,date,currency,amount_minor\nPAY-01,2026-10-20,IRR,'+amount+'\n').encode())
    def test_invalid_csv_header_and_extra_fields(self):
        for blob in [b'ref,date,currency,amount_minor\nA,2026-10-10,IRR,2\n',b'reference,date,currency,amount_minor\nA,2026-10-10,IRR,2,extra\n']:
            with self.assertRaises(InputRejected):parse_statement(blob)
    def test_spreadsheet_formula_ref_rejected(self):
        with self.assertRaises(InputRejected):parse_statement(b'reference,date,currency,amount_minor\n=HYPERLINK,2026-10-10,IRR,2\n')
    def test_invalid_dates_and_currencies(self):
        for date,curr in [('2026-02-30','IRR'),('2026/10/10','IRR'),('2026-10-10','BTC')]:
            with self.subTest(date=date,curr=curr),self.assertRaises(InputRejected):
                parse_statement(f'reference,date,currency,amount_minor\nA,{date},{curr},2\n'.encode())
    def test_statement_too_large_rejected(self):
        with self.assertRaises(InputRejected):parse_statement(b'x'*2_000_001)
    def test_missing_db_never_created(self):
        path=self.root/'missing.db'
        with self.assertRaises(InputRejected):open_readonly(path)
        self.assertFalse(path.exists())
    def test_symlink_database_rejected(self):
        alias=self.root/'alias.db';alias.symlink_to(self.db)
        with self.assertRaises(InputRejected):open_readonly(alias)
    def test_write_disallowed(self):
        with self.read_db() as conn:
            with self.assertRaises(sqlite3.OperationalError):conn.execute("UPDATE journal_entries SET doc_no='tamper'")
    def test_unsupported_or_nonasset_account(self):
        with self.read_db() as conn:
            with self.assertRaises(InputRejected):bank_ledger(conn,'2000')
            with self.assertRaises(InputRejected):bank_ledger(conn,'ABC')
    def test_unbalanced_journal_fails_closed(self):
        with sqlite3.connect(self.db) as conn:conn.execute('UPDATE journal_lines SET debit=2400 WHERE id=1')
        with self.read_db() as conn:
            with self.assertRaises(InputRejected):bank_ledger(conn,'1010')
    def test_aging_overpayment_rejected(self):
        with sqlite3.connect(self.db) as conn:conn.execute("INSERT INTO invoice_payments(invoice_id,amount,paid_on) VALUES(1,20000,'2026-10-22')")
        with self.read_db() as conn:
            with self.assertRaises(InputRejected):aging(conn,dt.date(2026,10,30))
    def test_multiple_currency_not_netting(self):
        with sqlite3.connect(self.db) as conn:
            conn.executescript("INSERT INTO journal_entries VALUES(3,'USD-1','2026-10-20'); INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(3,1,100,0,'USD'),(3,2,0,100,'USD');")
        bank=b'reference,date,currency,amount_minor\nPAY-01,2026-10-20,IRR,2500\nPAY-02,2026-10-22,IRR,-800\nUSD-1,2026-10-20,USD,100\n'
        with self.read_db() as conn:r=reconcile(conn,parse_statement(bank))
        self.assertEqual(r['currency_totals']['USD']['ledger_net_minor'],100)
        self.assertEqual(r['status'],'BALANCED_MATCHED')
    def test_invalid_lag_rejected(self):
        with self.read_db() as conn:
            with self.assertRaises(InputRejected):reconcile(conn,parse_statement(self.statement.read_bytes()),max_date_lag=70)
    def test_wrong_schema_rejected(self):
        path=self.root/'fake.sqlite3'
        with sqlite3.connect(path) as conn:conn.execute('CREATE TABLE nonsense(id INT)')
        with self.assertRaises(InputRejected):open_readonly(path)
    def test_future_statement_cutoff_rejected(self):
        self.statement.write_bytes(b'reference,date,currency,amount_minor\nPAY-01,2026-11-20,IRR,2500\n')
        with self.assertRaises(InputRejected):run(self.db,self.statement,'2026-10-30')
    def test_future_ledger_not_included_asof(self):
        with sqlite3.connect(self.db) as conn:
            conn.executescript("INSERT INTO journal_entries VALUES(3,'FUTURE','2026-11-20'); INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(3,1,1200,0,'IRR'),(3,2,0,1200,'IRR');")
        result=run(self.db,self.statement,'2026-10-30')['reconciliation']
        self.assertEqual(result['status'],'BALANCED_MATCHED')
        self.assertEqual(result['ledger_only_count'],0)
    def test_statement_rejects_forged_newline_reference(self):
        bad=b'reference,date,currency,amount_minor\n"A\nB",2026-10-20,IRR,10\n'
        with self.assertRaises(InputRejected):parse_statement(bad)
    def test_offline_result_disclaims_external_bank(self):
        r=run(self.db,self.statement,'2026-10-30')
        self.assertFalse(r['reconciliation']['represents_real_bank_authorization'])
        self.assertEqual(r['source'],'offline_only_not_bank_connected')


if __name__=='__main__':unittest.main(verbosity=2)