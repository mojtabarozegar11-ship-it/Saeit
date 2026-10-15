"""Exact-lineage 0048 factory inventory tests on synthetic SQLite only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"astra_stage45_legacy_gap_inventory.py"
spec=importlib.util.spec_from_file_location("astra_legacy_gap_tests",SCRIPT)
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class LegacyGapTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=self.root/"factory-fresh-isolated.sqlite3"
        with sqlite3.connect(self.db) as c:
            c.executescript("""
              CREATE TABLE django_migrations (app TEXT,name TEXT);
              INSERT INTO django_migrations VALUES('core','0048_business_market_architecture');
              CREATE TABLE core_product (id INTEGER PRIMARY KEY,factory_managed INTEGER,active INTEGER);
              CREATE TABLE core_factoryrun (id INTEGER PRIMARY KEY,product_id INTEGER);
              CREATE TABLE core_researchproject (id INTEGER PRIMARY KEY,factory_run_id INTEGER);
              CREATE TABLE core_researchsource (id INTEGER PRIMARY KEY,project_id INTEGER);
              CREATE TABLE core_evidence (id INTEGER PRIMARY KEY,project_id INTEGER,source_id INTEGER);
              INSERT INTO core_product VALUES (1,1,0),(2,1,0),(3,1,1),(4,0,0);
              INSERT INTO core_factoryrun VALUES (10,1),(11,2),(12,3);
              INSERT INTO core_researchproject VALUES (20,10),(21,11),(22,12);
              INSERT INTO core_researchsource VALUES (30,20),(31,20),(32,21),(33,22);
              INSERT INTO core_evidence VALUES (40,20,30),(41,20,30),
                  (42,21,32),(43,20,32),(44,22,33);
            """)

    def test_real_link_only_never_crosses_projects_or_active_records(self):
        result=audit.inventory(self.db)
        self.assertEqual(result["total_unpublished_factory_managed_products"],2)
        self.assertEqual(result["linked_source_rows_counted"],2)
        self.assertEqual(result["products_with_at_least_one_linked_source"],2)
        items={r["internal_product_id"]:r for r in result["worklist"]}
        self.assertEqual(set(items),{1,2})
        self.assertEqual(items[1]["preliminary_linked_source_rows"],1)
        self.assertEqual(items[1]["preliminary_evidence_rows"],2)
        self.assertEqual(items[2]["preliminary_linked_source_rows"],1)
        self.assertEqual(items[2]["preliminary_evidence_rows"],1)
        self.assertEqual(result["independently_verified_commercial_products"],0)
        self.assertIsNone(items[1]["commercial_quality_score"])
        self.assertFalse(items[1]["public_sale_authorized"])
        self.assertEqual(items[2]["independent_evidence_target"],100)

    def test_no_evidence_is_not_fake_counted(self):
        with sqlite3.connect(self.db) as c:
            c.execute("DELETE FROM core_evidence")
        result=audit.inventory(self.db)
        self.assertEqual(result["linked_source_rows_counted"],0)
        self.assertEqual(result["products_with_at_least_one_linked_source"],0)

    def test_missing_migration_or_schema_fails_closed(self):
        with sqlite3.connect(self.db) as c:
            c.execute("DELETE FROM django_migrations")
        with self.assertRaisesRegex(ValueError,"VPS-aligned"):
            audit.inventory(self.db)
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO django_migrations VALUES('core','0048_business_market_architecture')")
            c.execute("DROP TABLE core_evidence")
        with self.assertRaisesRegex(ValueError,"schema unavailable"):
            audit.inventory(self.db)

    def test_readonly_cli_permissions_and_source_hash_unchanged(self):
        before=hashlib.sha256(self.db.read_bytes()).digest()
        out=self.root/"research-gap.json"
        result=subprocess.run(
            [sys.executable,str(SCRIPT),"--db",str(self.db),"--out",str(out)],
            capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(out.read_text())["public_site_changes"],0)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).digest(),before)
        self.assertEqual(out.stat().st_mode & 0o777,0o600)
        self.assertIn("ASTRA_LEGACY_FACTORY_DATABASE_WRITES=0",result.stdout)

    def test_symlink_input_is_rejected(self):
        link=self.root/"symlinked.sqlite3"
        link.symlink_to(self.db)
        with self.assertRaisesRegex(ValueError,"symlinked"):
            audit.inventory(link)


if __name__=="__main__":
    unittest.main()
