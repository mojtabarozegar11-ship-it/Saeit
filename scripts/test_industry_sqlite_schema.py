#!/usr/bin/env python3
"""Exercise the actual embedded SQLite DDL in the PHP industry module."""
import re
import sqlite3
import unittest
from pathlib import Path

PHP=Path(__file__).resolve().parent.parent/'content/zomorod-business/industry_operations.php'


def schema(db: sqlite3.Connection):
    php=PHP.read_text(encoding='utf-8')
    # Only constant DDL strings. No PHP variables or live company data involved.
    statements=re.findall(r'\$db->exec\("(CREATE (?:TABLE|TRIGGER) IF NOT EXISTS.*?)"\);',php,re.S)
    statements+=re.findall(r"\$db->exec\('(CREATE INDEX IF NOT EXISTS.*?)'\);",php,re.S)
    if len(statements)!=10:
        raise AssertionError(f'Expected two tables, six triggers and two indexes; got {len(statements)}')
    db.execute('PRAGMA foreign_keys=ON')
    for statement in statements: db.execute(statement)


class IndustrySchemaTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        schema(self.db)
        self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,quantity,unit,created_by) VALUES('a','plot','P1','Demo','Synthetic only','planned',1,'ha',11)")
        self.db.execute("INSERT INTO industry_events(item_id,user_id,action,note) VALUES(1,11,'created','Synthetic only')")
    def tearDown(self): self.db.close()
    def test_unique_and_status_constraints(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,quantity,unit,created_by) VALUES('a','plot','P2','Demo','Synthetic','planned',1,'ha',11)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,quantity,unit,created_by) VALUES('b','crop','C1','Demo','Synthetic','retired',1,'ha',11)")
    def test_quantity_constraint(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,quantity,unit,created_by) VALUES('c','asset','A1','Demo','Synthetic','in_service',-1,'unit',11)")
    def test_audit_history_cannot_be_modified(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM industry_events WHERE id=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_events SET note='Changed' WHERE id=1")
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM industry_events').fetchone()[0],1)
    def test_fks(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO industry_events(item_id,user_id,action,note) VALUES(999,11,'made-up','Synthetic only')")
    def test_direct_sql_cannot_insert_released_batch(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,quantity,unit,created_by,reviewed_by,evidence_url,review_note) VALUES('direct','batch','B1','Batch','Synthetic','released',1,'unit',11,12,'https://example.org/e','Yes')")
    def test_direct_sql_cannot_change_identity(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET title='Tampered' WHERE id=1")
    def test_direct_sql_cannot_skip_status(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='resting' WHERE id=1")
    def test_direct_sql_cannot_self_approve_lab(self):
        self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,quantity,unit,created_by) VALUES('lab1','lab','L1','Lab','Synthetic','received',1,'sample',11)")
        self.db.execute("UPDATE industry_items SET status='testing' WHERE reference='L1'")
        self.db.execute("UPDATE industry_items SET status='review_required' WHERE reference='L1'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='verified',reviewed_by=11,evidence_url='https://example.org/e',review_note='Own approval' WHERE reference='L1'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='verified',reviewed_by=12,evidence_url='',review_note='No proof' WHERE reference='L1'")
        self.db.execute("UPDATE industry_items SET status='verified',reviewed_by=12,evidence_url='https://example.org/e',review_note='Reviewed' WHERE reference='L1'")
        self.assertEqual(self.db.execute("SELECT status FROM industry_items WHERE reference='L1'").fetchone()[0],'verified')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='rejected' WHERE reference='L1'")
    def test_direct_sql_cannot_skip_batch_hold(self):
        self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,quantity,unit,created_by) VALUES('batch1','batch','B1','Batch','Synthetic','planned',1,'unit',11)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='released',reviewed_by=12,evidence_url='https://example.org/e',review_note='Not tested' WHERE reference='B1'")
        self.db.execute("UPDATE industry_items SET status='producing' WHERE reference='B1'")
        self.db.execute("UPDATE industry_items SET status='quality_hold' WHERE reference='B1'")
        self.db.execute("UPDATE industry_items SET status='released',reviewed_by=12,evidence_url='https://example.org/e',review_note='Approved' WHERE reference='B1'")
    def test_direct_sql_denies_delete_and_invalid_parent(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('DELETE FROM industry_items WHERE id=1')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,parent_id,quantity,unit,created_by) VALUES('crop1','crop','C1','Crop','Synthetic','planned',999,1,'kg',11)")
        self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,parent_id,quantity,unit,created_by) VALUES('crop2','crop','C2','Crop','Synthetic','planned',1,1,'kg',11)")
    def test_direct_sql_rejects_reused_status_or_backdating(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='planned' WHERE id=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET created_at='1999-01-01' WHERE id=1")
    def test_plot_with_active_crop_cannot_retire(self):
        self.db.execute("INSERT INTO industry_items(request_key,kind,reference,title,detail,status,parent_id,quantity,unit,created_by) VALUES('c1','crop','C1','Crop','Synthetic','planned',1,1,'kg',11)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='retired' WHERE id=1")
        self.db.execute("UPDATE industry_items SET status='active' WHERE id=1")
        self.db.execute("UPDATE industry_items SET status='growing' WHERE reference='C1'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE industry_items SET status='retired' WHERE id=1")
        self.db.execute("UPDATE industry_items SET status='harvested' WHERE reference='C1'")
        self.db.execute("UPDATE industry_items SET status='retired' WHERE id=1")
    def test_sqlite_integrity(self):
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

if __name__=='__main__':unittest.main(verbosity=2)
