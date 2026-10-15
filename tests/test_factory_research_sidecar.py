"""Integration tests: private factory evidence sidecar cannot change DB or publish."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("factory_sidecar",
                                           str(ROOT/"scripts"/"factory_research_sidecar.py"))
sidecar=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sidecar)


class ResearchSidecarTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=self.root/"isolated.db"
        self.out=self.root/"private-report"
        with sqlite3.connect(str(self.db)) as connection:
            connection.executescript("""
            CREATE TABLE core_product(
              id INTEGER PRIMARY KEY, title TEXT, product_type TEXT, metadata TEXT,
              active INTEGER, price TEXT, owner_id INTEGER, knowledge_article_id INTEGER,
              factory_managed INTEGER);
            CREATE TABLE core_factoryrun(id INTEGER PRIMARY KEY, product_id INTEGER, status TEXT);
            CREATE TABLE core_researchproject(id INTEGER PRIMARY KEY, factory_run_id INTEGER);
            """)
            metadata=json.dumps({"factory_state":"needs_research","validation":{
                "outcome":"NEEDS_MORE_EVIDENCE","missing_factors":[
                    "market_demand","willingness_to_pay"]}})
            connection.executemany(
                "INSERT INTO core_product VALUES (?,?,?,?,?,?,?,?,?)",
                [(1,"Draft 1","digital",metadata,0,"0",None,None,1),
                 (2,"Draft 2","digital",metadata,0,"0",None,None,1),
                 (3,"Non-factory","digital",metadata,0,"0",None,None,0)])

    def test_evidence_worklist_has_no_order_or_publication_dependency(self):
        original=self.db.read_bytes()
        result=sidecar.inspect(self.db,self.out,limit=50)
        self.assertEqual(result["processed"],2)
        self.assertEqual(result["blocked"],2)
        self.assertTrue(result["changed"])
        self.assertEqual(self.db.read_bytes(),original)
        report=json.loads((self.out/"latest.json").read_text(encoding="utf-8"))
        self.assertEqual(report["product_count"],2)
        self.assertEqual(report["research_blocked"],2)
        self.assertFalse(report["commercial_quality_approved"])
        self.assertFalse(report["approval_bypass"])
        self.assertEqual(report["publishable_count"],0)
        self.assertEqual(report["database_mutations"],0)
        self.assertEqual(report["external_calls"],0)
        self.assertIn("ONE_HUNDRED_DISTINCT_STRONG_EVIDENCE_PASSAGES_REQUIRED",
                      report["blocker_frequency"])
        self.assertTrue(all(p["publish_authorized"] is False for p in report["products"]))
        self.assertEqual(stat.S_IMODE((self.out/"latest.json").stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode),0o700)

    def test_identical_snapshot_is_idempotent(self):
        first=sidecar.inspect(self.db,self.out,limit=50)
        second=sidecar.inspect(self.db,self.out,limit=50)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])

    def test_zero_products_is_valid(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE core_product SET factory_managed=0")
        out=sidecar.inspect(self.db,self.out)
        self.assertEqual(out["processed"],0)
        self.assertEqual(out["publishable"],0)


    def test_rotates_oversized_backlog_and_reports_unscanned(self):
        with sqlite3.connect(self.db) as c:
            template=c.execute("SELECT metadata FROM core_product WHERE id=1").fetchone()[0]
            c.execute("INSERT INTO core_product VALUES (?,?,?,?,?,?,?,?,?)",
                      (4,"Draft 4","digital",template,0,"0",None,None,1))
            c.execute("INSERT INTO core_product VALUES (?,?,?,?,?,?,?,?,?)",
                      (5,"Draft 5","digital",template,0,"0",None,None,1))
        first=sidecar.inspect(self.db,self.out,limit=2)
        data=json.loads((self.out/"latest.json").read_text(encoding="utf-8"))
        self.assertEqual([p["product_id"] for p in data["products"]],[1,2])
        self.assertEqual(data["total_factory_drafts_in_scope"],4)
        self.assertEqual(data["unscanned_in_this_batch"],2)
        self.assertEqual(first["unscanned"],2)
        second=sidecar.inspect(self.db,self.out,limit=2)
        data=json.loads((self.out/"latest.json").read_text(encoding="utf-8"))
        self.assertEqual([p["product_id"] for p in data["products"]],[4,5])
        self.assertTrue(second["changed"])
        sidecar.inspect(self.db,self.out,limit=2)
        data=json.loads((self.out/"latest.json").read_text(encoding="utf-8"))
        self.assertEqual([p["product_id"] for p in data["products"]],[1,2])

    def test_duplicate_titles_only_counted_not_disclosed(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE core_product SET title=? WHERE id=2",("  DRAFT   1  ",))
        sidecar.inspect(self.db,self.out,limit=50)
        report=json.loads((self.out/"latest.json").read_text(encoding="utf-8"))
        self.assertEqual(report["duplicate_title_occurrences_in_batch"],1)
        self.assertEqual(report["duplicate_title_groups_in_batch"],1)
        self.assertNotIn("DRAFT",str(report["blocker_frequency"]))

    def test_symlink_cursor_denied(self):
        self.out.mkdir()
        path=self.out/"cursor.json"
        path.symlink_to(self.root/"bad-destination")
        with self.assertRaisesRegex(RuntimeError,"CURSOR_SYMLINK"):
            sidecar.inspect(self.db,self.out,limit=50)

    def test_two_database_scopes_never_reconcile_by_id(self):
        other=self.root/"django.db"
        with sqlite3.connect(self.db) as original, sqlite3.connect(other) as mirror:
            original.backup(mirror)
        with sqlite3.connect(other) as mirror:
            mirror.execute("UPDATE core_product SET title=? WHERE id=1",("OTHER PRODUCT ID 1",))
            metadata=mirror.execute("SELECT metadata FROM core_product WHERE id=2").fetchone()[0]
            mirror.execute("INSERT INTO core_product VALUES (?,?,?,?,?,?,?,?,?)",
                           (4,"Django private candidate","digital",metadata,0,"0",None,None,1))
        before_a=self.db.read_bytes()
        before_b=other.read_bytes()
        sidecar.inspect(self.db,self.out,limit=50,compare_db=other)
        info=json.loads((self.out/"latest.json").read_text(encoding="utf-8"))
        diff=info["data_source_consistency"]
        self.assertFalse(diff["database_files_are_identical"])
        self.assertEqual(diff["private_product_count"],3)
        self.assertEqual(diff["django_product_count"],4)
        self.assertEqual(diff["overlapping_numeric_ids"],3)
        self.assertEqual(diff["overlap_ids_with_different_normalized_titles"],1)
        self.assertEqual(diff["django_only_numeric_ids"],1)
        self.assertEqual(diff["private_only_numeric_ids"],0)
        self.assertFalse(diff["auto_reconciliation_allowed"])
        self.assertEqual(before_a,self.db.read_bytes())
        self.assertEqual(before_b,other.read_bytes())

    def test_same_sqlite_path_is_detected_not_auto_reconciled(self):
        sidecar.inspect(self.db,self.out,compare_db=self.db)
        info=json.loads((self.out/"latest.json").read_text(encoding="utf-8"))
        self.assertTrue(info["data_source_consistency"]["database_files_are_identical"])
        self.assertFalse(info["data_source_consistency"]["auto_reconciliation_allowed"])

    def test_limit_requires_bounded_integer(self):
        for n in (0,101,-1,True,1.5):
            with self.subTest(limit=n),self.assertRaises(ValueError):
                sidecar.inspect(self.db,self.out,limit=n)

    def test_symlink_destination_denied(self):
        real=self.root/"actual"
        real.mkdir()
        target=self.root/"linked"
        target.symlink_to(real)
        with self.assertRaisesRegex(RuntimeError,"PRIVATE_OUT_SYMLINK"):
            sidecar.inspect(self.db,target)


if __name__=="__main__":
    unittest.main()
