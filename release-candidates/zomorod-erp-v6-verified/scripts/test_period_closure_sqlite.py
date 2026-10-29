#!/usr/bin/env python3
"""Offline SQLite DDL and concurrency regressions for period_controls.php.

Does not execute PHP business logic; test period_controls_synthetic_qa.php separately
in a PHP runtime with PDO_SQLite. All records below are synthetic.
"""
from __future__ import annotations
import pathlib
import re
import sqlite3
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parent.parent
SOURCE=(ROOT/'content/zomorod-business/period_controls.php').read_text()
DDL=re.findall(r'\$db->exec\("(CREATE (?:TABLE|TRIGGER|INDEX).*?)"\);',SOURCE,re.S)

class PeriodSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='zm-period-sqlite-')
        self.path=pathlib.Path(self.temp.name)/'company-test.sqlite3'
        self.db=sqlite3.connect(self.path,timeout=.75,isolation_level=None)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY,role TEXT);
            INSERT INTO users VALUES(1,'accountant'),(2,'admin');
            CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_no TEXT,doc_date TEXT);
            CREATE TABLE journal_lines(id INTEGER PRIMARY KEY,entry_id INTEGER REFERENCES journal_entries(id),
                account_id INTEGER,currency TEXT,debit INTEGER,credit INTEGER);
            CREATE TABLE invoices(id INTEGER PRIMARY KEY,invoice_date TEXT,invoice_no TEXT,posted_entry INTEGER);
            CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY,invoice_id INTEGER REFERENCES invoices(id),paid_on TEXT,amount INTEGER,entry_id INTEGER);
            INSERT INTO invoices VALUES(1,'2026-10-03','SYNTH-INV',1),(2,'2026-09-05','PAST-INV',NULL);
            INSERT INTO invoice_payments VALUES(1,1,'2026-10-08',10000,2);
            INSERT INTO journal_entries VALUES(1,'SYNTH-OLD','2026-10-03');
            INSERT INTO journal_lines VALUES(1,1,100,'IRR',10000,0),(2,1,200,'IRR',0,10000);
        ''')
        for sql in DDL:self.db.execute(sql)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def freeze(self):
        self.db.execute("INSERT INTO zm_accounting_periods(period_key,state,requested_by,snapshot_sha256,request_note) VALUES('2026-10','pending',1,?,?)",('a'*64,'Synthetic'))

    def assert_denied(self,sql,params=()):
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute(sql,params)

    def test_schema_and_invariant_ddl_installs(self):
        self.assertGreaterEqual(len(DDL),13)
        trig={r[0] for r in self.db.execute('SELECT name FROM sqlite_master WHERE type="trigger"')}
        for name in ('zm_period_guard_entry_insert','zm_period_guard_entry_update',
            'zm_period_guard_entry_delete','zm_period_guard_line_insert',
            'zm_period_guard_line_update','zm_period_guard_line_delete',
            'zm_period_events_no_update','zm_period_events_no_delete'):
            self.assertIn(name,trig)

    def test_duplicate_posting_insert_across_document_types_blocked(self):
        # Two invoices must not share one posting, even in an open month.
        self.assert_denied("INSERT INTO invoices VALUES(3,'2026-11-01','DUP-INV',1)")
        # Payment posting id=2 is already assigned; a second payment cannot reuse it.
        self.assert_denied("INSERT INTO invoice_payments VALUES(3,1,'2026-11-01',100,2)")
        # Invoice must not point at a posting already used by a payment.
        self.assert_denied("INSERT INTO invoices VALUES(3,'2026-11-01','DUP-CROSS',2)")

    def test_duplicate_posting_update_across_document_types_blocked(self):
        self.assert_denied('UPDATE invoices SET posted_entry=2 WHERE id=1')
        self.assert_denied('UPDATE invoice_payments SET entry_id=1 WHERE id=1')
        # Control: a genuinely unlinked posting can be referenced once.
        self.db.execute("INSERT INTO invoices VALUES(3,'2026-11-01','SAFE-NEW',4)")
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],3)

    def test_pending_period_blocks_direct_legacy_sql_writes(self):
        self.freeze()
        self.assert_denied("INSERT INTO journal_entries VALUES(2,'EVASION','2026-10-15')")
        self.assert_denied("UPDATE journal_entries SET doc_date='2026-11-03' WHERE id=1")
        self.assert_denied('DELETE FROM journal_entries WHERE id=1')
        self.assert_denied("INSERT INTO journal_lines VALUES(3,1,300,'IRR',20,0)")
        self.assert_denied('UPDATE journal_lines SET debit=10001 WHERE id=1')
        self.assert_denied('DELETE FROM journal_lines WHERE id=1')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM journal_entries').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM journal_lines').fetchone()[0],2)

    def test_frozen_invoice_cannot_be_inserted_updated_or_deleted(self):
        self.freeze()
        self.assert_denied("INSERT INTO invoices VALUES(3,'2026-10-12','BACKDATE',3)")
        self.assert_denied("UPDATE invoices SET invoice_no='EDIT' WHERE id=1")
        self.assert_denied("UPDATE invoices SET invoice_date='2026-11-01' WHERE id=1")
        self.assert_denied("UPDATE invoices SET invoice_date='2026-10-01' WHERE id=2")
        self.assert_denied('DELETE FROM invoices WHERE id=1')
        self.assertEqual(self.db.execute("SELECT invoice_no FROM invoices WHERE id=1").fetchone()[0],'SYNTH-INV')

    def test_frozen_payment_cannot_be_inserted_updated_or_deleted(self):
        self.freeze()
        self.assert_denied("INSERT INTO invoice_payments VALUES(2,1,'2026-10-09',100,3)")
        self.assert_denied("UPDATE invoice_payments SET amount=11111 WHERE id=1")
        self.assert_denied("UPDATE invoice_payments SET paid_on='2026-11-01' WHERE id=1")
        self.assert_denied('DELETE FROM invoice_payments WHERE id=1')
        # A later settlement of a previously issued invoice is in an open period.
        self.db.execute("INSERT INTO invoice_payments VALUES(2,1,'2026-11-02',100,3)")
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM invoice_payments').fetchone()[0],2)

    def test_period_guard_survives_concurrent_historical_invoice_attempt(self):
        self.freeze()
        competitor=sqlite3.connect(self.path,timeout=.15,isolation_level=None)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                competitor.execute("UPDATE invoices SET invoice_no='RACE' WHERE id=1")
        finally:
            competitor.close()

    def test_open_month_allows_accounting_writes(self):
        self.freeze()
        self.db.execute("INSERT INTO journal_entries VALUES(2,'OPEN','2026-11-01')")
        self.db.execute("INSERT INTO journal_lines VALUES(3,2,100,'IRR',500,0)")
        self.db.execute("INSERT INTO journal_lines VALUES(4,2,200,'IRR',0,500)")
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM journal_entries').fetchone()[0],2)

    def test_database_rejects_forged_approval_and_reopening(self):
        self.assert_denied("INSERT INTO zm_accounting_periods(period_key,state,requested_by,snapshot_sha256,request_note) VALUES('2026-09','closed',1,?,?)",('b'*64,'forged'))
        self.freeze()
        self.assert_denied("UPDATE zm_accounting_periods SET state='closed',approved_by=1,decision_note='self' WHERE period_key='2026-10'")
        self.db.execute("UPDATE zm_accounting_periods SET state='closed',approved_by=2,decision_note='independent' WHERE period_key='2026-10'")
        self.assert_denied("UPDATE zm_accounting_periods SET state='pending' WHERE period_key='2026-10'")
        self.assert_denied("UPDATE zm_accounting_periods SET snapshot_sha256=? WHERE period_key='2026-10'",('c'*64,))

    def test_closed_period_remains_immutable(self):
        self.freeze()
        self.db.execute("UPDATE zm_accounting_periods SET state='closed',approved_by=2,decision_note='independent' WHERE period_key='2026-10'")
        self.assert_denied('DELETE FROM zm_accounting_periods')
        self.assert_denied('UPDATE journal_lines SET credit=9999 WHERE id=2')

    def test_audit_cannot_be_rewritten(self):
        self.freeze()
        self.db.execute("INSERT INTO zm_period_events(period_key,actor_id,event,note) VALUES('2026-10',1,'freeze_requested','Synthetic')")
        self.assert_denied("UPDATE zm_period_events SET note='fabricated' WHERE id=1")
        self.assert_denied('DELETE FROM zm_period_events')

    def test_concurrent_writer_waits_and_then_fails_closed(self):
        competitor=sqlite3.connect(self.path,timeout=.15,isolation_level=None)
        try:
            competitor.execute('PRAGMA busy_timeout=100')
            self.db.execute('BEGIN IMMEDIATE')
            self.freeze()
            with self.assertRaises(sqlite3.OperationalError):
                competitor.execute("INSERT INTO journal_entries VALUES(2,'RACE','2026-10-20')")
            self.db.execute('COMMIT')
            with self.assertRaises(sqlite3.IntegrityError):
                competitor.execute("INSERT INTO journal_entries VALUES(2,'RACE','2026-10-20')")
        finally:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            competitor.close()

    def test_application_routes_and_posting_guard_present(self):
        app=(ROOT/'content/zomorod-business/app.php').read_text()
        for text in ("require_once $private.'/period_controls.php'",'zmPeriodSchema($db)',
                     'zmPeriodGuard($db,$date)',"'period_controls'=>'بستن دورهٔ مالی'",
                     "'period_freeze','period_close'",'zmPeriodRender($db)'):
            self.assertIn(text,app)

if __name__=='__main__':unittest.main(verbosity=2)
