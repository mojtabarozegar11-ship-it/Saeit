"""Private VPS research bridge: standalone Python 3.8+, never original-factory writes."""
import importlib.util
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "astra_standalone_bridge", HERE/"scripts/astra_v2_private_research_bridge.py")
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ResearchBridgeTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        (self.root/"existing").mkdir()
        (self.root/"private").mkdir()
        self.src=self.root/"existing"/"original.sqlite3"
        self.dest=self.root/"private"/"research.sqlite3"
        with sqlite3.connect(str(self.src)) as db:
            db.executescript("""
            CREATE TABLE core_product(id INTEGER PRIMARY KEY,
                factory_managed INTEGER NOT NULL,active INTEGER NOT NULL);
            CREATE TABLE core_factoryrun(id INTEGER PRIMARY KEY,product_id INTEGER);
            CREATE TABLE core_researchproject(id INTEGER PRIMARY KEY,factory_run_id INTEGER);
            CREATE TABLE core_researchsource(id INTEGER PRIMARY KEY,project_id INTEGER);
            CREATE TABLE core_evidence(id INTEGER PRIMARY KEY,project_id INTEGER,source_id INTEGER);
            INSERT INTO core_product VALUES
               (1,1,0),(2,1,0),(3,0,0),(4,1,1),(5,1,0);
            INSERT INTO core_factoryrun VALUES (10,1);
            INSERT INTO core_researchproject VALUES (20,10);
            INSERT INTO core_researchsource VALUES (30,20),(31,20);
            INSERT INTO core_evidence VALUES (40,20,30),(41,20,31);
            """)

    def test_private_tick_creates_hypotheses_not_products(self):
        x=bridge.tick(self.src,self.dest,limit=10)
        self.assertEqual(x["new_research_tasks"],3)
        self.assertEqual(x["total_research_tasks"],3)
        self.assertFalse(x["payment_activated"])
        self.assertFalse(x["publication_authorized"])
        with sqlite3.connect(str(self.dest)) as db:
            rows=db.execute(
                "SELECT legacy_product_id,source_refs_unverified,evidence_refs_unverified "
                "FROM research_tasks ORDER BY legacy_product_id").fetchall()
        self.assertEqual(rows,[(1,2,2),(2,0,0),(5,0,0)])

    def test_no_duplicate_on_repeat_or_wrap(self):
        x=bridge.tick(self.src,self.dest,limit=2)
        self.assertEqual(x["new_research_tasks"],2)
        y=bridge.tick(self.src,self.dest,limit=2)
        self.assertEqual(y["new_research_tasks"],1)
        self.assertEqual(y["total_research_tasks"],3)
        z=bridge.tick(self.src,self.dest,limit=2)
        self.assertTrue(z["wrapped"])
        self.assertEqual(z["new_research_tasks"],0)
        self.assertEqual(z["total_research_tasks"],3)

    def test_counts_can_be_refreshed_but_reviewed_tasks_are_immutable(self):
        bridge.tick(self.src,self.dest,limit=10)
        with sqlite3.connect(str(self.src)) as db:
            db.execute("INSERT INTO core_researchsource VALUES(32,20)")
        x=bridge.tick(self.src,self.dest,limit=10)
        self.assertEqual(x["updated_count_only"],1)
        with sqlite3.connect(str(self.dest)) as db:
            db.execute("UPDATE research_tasks SET stage='REVIEW_REQUIRED' WHERE legacy_product_id=1")
        with sqlite3.connect(str(self.src)) as db:
            db.execute("INSERT INTO core_researchsource VALUES(33,20)")
        y=bridge.tick(self.src,self.dest,limit=10)
        self.assertEqual(y["updated_count_only"],0)
        with sqlite3.connect(str(self.dest)) as db:
            row=db.execute(
                "SELECT source_refs_unverified,stage FROM research_tasks "
                "WHERE legacy_product_id=1").fetchone()
        self.assertEqual(row,(3,"REVIEW_REQUIRED"))

    def test_original_db_bytes_never_changed(self):
        start=hashlib.sha256(self.src.read_bytes()).digest()
        bridge.tick(self.src,self.dest)
        bridge.tick(self.src,self.dest,check=True)
        end=hashlib.sha256(self.src.read_bytes()).digest()
        self.assertEqual(start,end)

    def test_health_uses_read_only_private_db(self):
        bridge.tick(self.src,self.dest)
        check=bridge.tick(self.src,self.dest,check=True)
        self.assertEqual(check["research_tasks"],3)
        self.assertEqual(check["mode"],"READ_ONLY_HEALTH")
        self.assertTrue(check["last_tick_utc"])
        self.assertEqual(check["commercially_qualified"],0)

    def test_sql_constraints_reject_sale_ready_bypass(self):
        bridge.tick(self.src,self.dest)
        with sqlite3.connect(str(self.dest)) as db:
            for statement in (
                "UPDATE research_tasks SET sale_ready=1",
                "UPDATE research_tasks SET market_demand_verified=1",
                "UPDATE research_tasks SET quality_score=100",
            ):
                with self.subTest(statement=statement):
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(statement)

    def test_refuse_same_directory_or_database_source(self):
        with self.assertRaisesRegex(ValueError,"SEPARATE_DIRECTORY"):
            bridge.tick(self.src,self.root/"existing"/"other.sqlite3")
        with self.assertRaises(ValueError):
            bridge.tick(self.src,self.src)

    def test_refuse_source_or_private_symlink(self):
        link=self.root/"fake-source.sqlite3"
        link.symlink_to(self.src)
        with self.assertRaisesRegex(ValueError,"SOURCE_DB_MISSING_OR_SYMLINK"):
            bridge.tick(link,self.dest)
        bridge.tick(self.src,self.dest)
        link2=self.root/"private"/"danger.sqlite3"
        link2.symlink_to(self.dest)
        with self.assertRaisesRegex(ValueError,"PRIVATE_DB_PATH_NOT_ALLOWED"):
            bridge.tick(self.src,link2)

    def test_reject_source_schema_without_mutations(self):
        with sqlite3.connect(str(self.src)) as db:
            db.execute("DROP TABLE core_researchsource")
        with self.assertRaisesRegex(ValueError,"SOURCE_SCHEMA_MISSING"):
            bridge.tick(self.src,self.dest)
        with sqlite3.connect(str(self.src)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM core_product").fetchone()[0],5)

    def test_reject_out_of_bounds_batch(self):
        for batch in (0,51,-1):
            with self.subTest(limit=batch), self.assertRaisesRegex(ValueError,"BATCH_LIMIT_OUT_OF_RANGE"):
                bridge.tick(self.src,self.dest,limit=batch)

    def test_no_original_data_content_is_copied(self):
        bridge.tick(self.src,self.dest)
        text="".join([str(r) for r in sqlite3.connect(str(self.dest)).execute(
            "SELECT * FROM research_tasks")])
        self.assertIn("legacy-factory-product:1",text)
        self.assertNotIn("fictional-raw-passages",text)


if __name__=="__main__":
    unittest.main()
