"""Tests isolated first-product preparation: never mutate the factory database."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "factory_first_product_pilot.py"
spec = importlib.util.spec_from_file_location("factory_pilot", str(SCRIPT))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class FirstProductPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "factory.sqlite3"
        with sqlite3.connect(str(self.db)) as con:
            con.executescript("""
                CREATE TABLE core_product(id INTEGER PRIMARY KEY,title TEXT,product_type TEXT,
                    metadata TEXT,active BOOLEAN,price TEXT,owner_id INTEGER,
                    knowledge_article_id INTEGER,factory_managed BOOLEAN);
                CREATE TABLE core_factoryrun(id INTEGER PRIMARY KEY,product_id INTEGER,status TEXT);
                CREATE TABLE core_researchproject(id INTEGER PRIMARY KEY,factory_run_id INTEGER,status TEXT);
                CREATE TABLE core_researchsource(id INTEGER PRIMARY KEY,project_id INTEGER,title TEXT,
                    publisher TEXT,url TEXT);
                CREATE TABLE core_evidence(id INTEGER PRIMARY KEY,project_id INTEGER,source_id INTEGER,
                    passage TEXT,confidence TEXT);
                CREATE TABLE core_finding(id INTEGER PRIMARY KEY,project_id INTEGER,
                    statement TEXT,limitation TEXT,confidence TEXT);
                CREATE TABLE core_report(id INTEGER PRIMARY KEY,project_id INTEGER,
                    title TEXT,status TEXT,content TEXT);
            """)
            metadata = {"factory_state":"needs_research","validation":{
                "outcome":"NEEDS_MORE_EVIDENCE",
                "missing_factors":["external evidence","customer demand"]}}
            con.execute("INSERT INTO core_product VALUES(1,?,?,?,?,?,?,?,?)",
                        ("Internal example","digital",json.dumps(metadata),0,"0",None,None,1))
            con.execute("INSERT INTO core_factoryrun VALUES(10,1,?)",("active",))
            con.execute("INSERT INTO core_researchproject VALUES(11,10,?)",("evidence_collected",))
            con.execute("INSERT INTO core_researchsource VALUES(12,11,?,?,?)",
                        ("Research source","Example university","https://example.edu/study"))
            con.execute("INSERT INTO core_evidence VALUES(13,11,12,?,?)",
                        ("Existing record; not independently verified","0.5"))
            con.execute("INSERT INTO core_report VALUES(14,11,?,?,?)",
                        ("Draft report","draft",json.dumps({"summary":"Unverified working notes"})))

    def test_blocks_unvalidated_product(self):
        with sqlite3.connect(self.db.as_uri()+"?mode=ro",uri=True) as con:
            con.row_factory = sqlite3.Row
            pack = pilot.prepare(con)
        self.assertEqual(pack["product_id"],1)
        self.assertEqual(len(pack["missing_factors"]),2)
        self.assertIn("NO_POSITIVE_PRICE",pack["issues"])
        self.assertIn("VALIDATION_NOT_PASSED",pack["issues"])
        self.assertIn("NOT FOR SALE",pilot.draft_markdown(pack))

    def test_private_draft_is_idempotent_and_database_unchanged(self):
        previous = self.db.read_bytes()
        output = Path(self.temp.name) / "private"
        args = ["--db",str(self.db),"--out",str(output),"--prepare"]
        self.assertEqual(pilot.main(args),0)
        self.assertEqual(pilot.main(args),0)
        self.assertEqual(self.db.read_bytes(),previous)
        self.assertTrue((output/"product-1"/"internal_draft.md").exists())
        self.assertEqual((output/"product-1"/"internal_draft.md").stat().st_mode & 0o777,0o600)

    def test_nonexistent_product_does_not_create_files(self):
        output = Path(self.temp.name) / "private"
        with self.assertRaises(RuntimeError):
            pilot.main(["--db",str(self.db),"--out",str(output),
                        "--product-id","999","--prepare"])
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
