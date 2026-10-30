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
    if len(statements)!=6:
        raise AssertionError(f'Expected two tables, two triggers and two indexes; got {len(statements)}')
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
    def test_sqlite_integrity(self):
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

if __name__=='__main__':unittest.main(verbosity=2)
