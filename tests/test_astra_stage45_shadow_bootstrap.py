"""Private 0049 shadow seeding regression: only a disposable SQLite fixture."""
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"astra_stage45_shadow_bootstrap.py"
spec=importlib.util.spec_from_file_location("astra45_shadow_bootstrap_tests",SCRIPT)
bootstrap=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class Stage45ShadowTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.source=self.root/"factory-fresh-isolated.sqlite3"
        self.shadow=self.root/"astra-v2-stage45-shadow-deadbeef1234.sqlite3"
        with sqlite3.connect(self.source) as c:
            c.executescript("""
                CREATE TABLE django_migrations (app TEXT,name TEXT);
                INSERT INTO django_migrations VALUES
                    ('core','0048_business_market_architecture');
                CREATE TABLE core_product (
                    id INTEGER PRIMARY KEY, factory_managed INTEGER, active INTEGER);
                INSERT INTO core_product VALUES (3,1,0),(7,1,0),(9,1,1),(10,0,0);
            """)
        with sqlite3.connect(self.shadow) as c:
            c.executescript("""
                CREATE TABLE django_migrations (app TEXT,name TEXT);
                INSERT INTO django_migrations VALUES
                    ('core','0048_business_market_architecture'),
                    ('core','0049_astra_stage45_research_queue');
                CREATE TABLE core_factoryqueueitem (
                    id INTEGER PRIMARY KEY,created_at TEXT,updated_at TEXT,
                    key TEXT NOT NULL UNIQUE, kind TEXT,status TEXT,
                    priority_score NUMERIC,
                    evidence_verified_independently INTEGER NOT NULL DEFAULT 0,
                    build_authorized INTEGER NOT NULL DEFAULT 0,
                    publish_authorized INTEGER NOT NULL DEFAULT 0,
                    payment_authorized INTEGER NOT NULL DEFAULT 0,
                    CHECK (evidence_verified_independently=0 AND
                           build_authorized=0 AND publish_authorized=0 AND
                           payment_authorized=0));
                CREATE TABLE core_discoverysnapshot (id INTEGER PRIMARY KEY);
            """)

    def test_creates_only_two_research_rows_and_is_idempotent(self):
        hash_before=hashlib.sha256(self.source.read_bytes()).hexdigest()
        first=bootstrap.prepare(self.source,self.shadow)
        second=bootstrap.prepare(self.source,self.shadow)
        self.assertEqual(first,second)
        self.assertEqual(first["topics_needing_independent_research"],2)
        self.assertEqual(first["evidence_target_per_candidate"],100)
        self.assertEqual(first["public_releases"],0)
        self.assertFalse(first["payments_enabled"])
        with sqlite3.connect(self.shadow) as c:
            rows=c.execute(
                "SELECT key,kind,status,priority_score,build_authorized,"
                "publish_authorized,payment_authorized "
                "FROM core_factoryqueueitem ORDER BY key"
            ).fetchall()
        self.assertEqual(rows,[
            ("research:legacy-product:3","discovery","RESEARCH_REQUIRED",None,0,0,0),
            ("research:legacy-product:7","discovery","RESEARCH_REQUIRED",None,0,0,0),
        ])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),hash_before)

    def test_refuses_wrong_source_version(self):
        with sqlite3.connect(self.source) as c:
            c.execute("UPDATE django_migrations SET name='0047_old'")
        with self.assertRaisesRegex(ValueError,"SOURCE_NOT_0048"):
            bootstrap.prepare(self.source,self.shadow)

    def test_refuses_target_schema_without_0049(self):
        with sqlite3.connect(self.shadow) as c:
            c.execute("DELETE FROM django_migrations WHERE name LIKE '0049%'")
        with self.assertRaisesRegex(ValueError,"TARGET_NOT_0049"):
            bootstrap.prepare(self.source,self.shadow)

    def test_refuses_preexisting_authorized_or_unrelated_rows(self):
        with sqlite3.connect(self.shadow) as c:
            c.execute("INSERT INTO core_factoryqueueitem "
                      "(key,kind,status,build_authorized,publish_authorized,payment_authorized,"
                      "evidence_verified_independently) "
                      "VALUES ('not-a-research-topic','discovery','RESEARCH_REQUIRED',0,0,0,0)")
        with self.assertRaisesRegex(ValueError,"NONRESEARCH_QUEUE_OR_AUTHORIZATION"):
            bootstrap.prepare(self.source,self.shadow)

    def test_symlink_and_production_named_targets_forbidden(self):
        alias=self.root/"astra-v2-stage45-shadow-abcdefabcdef.sqlite3"
        alias.symlink_to(self.shadow)
        with self.assertRaisesRegex(ValueError,"NO_SYMLINK"):
            bootstrap.prepare(self.source,alias)
        live=self.root/"factory-production.sqlite3"
        live.write_bytes(self.shadow.read_bytes())
        with self.assertRaisesRegex(ValueError,"REFUSE_NONPRIVATE_DB_NAME"):
            bootstrap.prepare(self.source,live)


if __name__=="__main__":
    unittest.main()
