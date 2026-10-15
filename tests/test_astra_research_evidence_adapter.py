"""Astra research adapter tests against synthetic SQLite, never a live server."""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_research_evidence_adapter.py"
spec = importlib.util.spec_from_file_location("astra_adapter_tests", SCRIPT)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
NOW = "2026-10-15T00:00:00Z"
MEASURES = {
    "problem_intensity": 85, "demand": 80, "differentiation": 70,
    "feasibility": 80, "margin": 70, "distribution": 90, "strategic_fit": 85,
}
GATES = {
    "lawful": True, "rights_reviewed": True,
    "build_capability_available": True, "distribution_path_available": True,
}


def item(key, **extra):
    return dict(
        opportunity_key=key,
        problem="Synthetic farm budgeting scenario; no asserted real demand",
        assessments=dict(MEASURES), gates=dict(GATES), **extra,
    )


def hash_for(s):
    return hashlib.sha256(s.encode()).hexdigest()


class AdapterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.db = self.home / "factory.sqlite3"
        with sqlite3.connect(self.db) as conn:
            conn.executescript("""
                CREATE TABLE core_product (
                  id INTEGER PRIMARY KEY, factory_managed INTEGER, active INTEGER);
                CREATE TABLE core_factoryrun (
                  id INTEGER PRIMARY KEY, product_id INTEGER, status TEXT);
                CREATE TABLE core_researchproject (
                  id INTEGER PRIMARY KEY, factory_run_id INTEGER);
                CREATE TABLE core_researchsource (
                  id INTEGER PRIMARY KEY, project_id INTEGER, url TEXT,
                  content_hash TEXT);
                CREATE TABLE core_evidence (
                  id INTEGER PRIMARY KEY, project_id INTEGER, source_id INTEGER);
                INSERT INTO core_product VALUES (1,1,0),(2,0,0),(3,1,1);
                INSERT INTO core_factoryrun VALUES (10,1,'active'),(20,2,'active'),
                  (30,3,'active');
                INSERT INTO core_researchproject VALUES (100,10),(200,20),(300,30);
                INSERT INTO core_researchsource VALUES
                  (1000,100,'https://example.com/a','abc'),
                  (1001,100,'https://example.org/b','def'),
                  (2000,200,'https://unrelated.example.net/c','other'),
                  (3000,300,'https://published.example.net/d','other');
                INSERT INTO core_evidence VALUES
                  (5000,100,1000),(5001,100,1001),
                  (5002,200,2000),(5003,300,3000);
            """)

    def test_existing_real_source_schema_is_not_inferred_buying_demand(self):
        original = self.db.read_bytes()
        report = adapter.evaluate_db(self.db, [item("orchard", product_id=1)], NOW)
        row = report["candidates"][0]
        self.assertEqual(row["status"], "RESEARCH_REQUIRED")
        self.assertEqual(row["distinct_source_domains_preliminary"], 0)
        self.assertEqual(report["bridge_audit"]["legacy_references_review_only"], 2)
        self.assertFalse(report["bridge_audit"]["astra_0049_schema_available"])
        self.assertFalse(row["build_authorized"])
        self.assertEqual(original, self.db.read_bytes())

    def test_website_product_and_active_item_sources_not_cross_assigned(self):
        r = adapter.evaluate_db(self.db, [
            item("website", product_id=2), item("active", product_id=3),
            item("factory", product_id=1),
        ], NOW)
        self.assertEqual(r["bridge_audit"]["legacy_references_review_only"], 2)

    def test_unknown_product_links_cannot_match_another_project(self):
        report = adapter.evaluate_db(self.db, [item("unknown", product_id=44)], NOW)
        self.assertEqual(report["bridge_audit"]["legacy_references_examined"], 0)

    def test_optional_astra_discovery_snapshot_maps_exact_queue_key_only(self):
        with sqlite3.connect(self.db) as conn:
            conn.executescript("""
              CREATE TABLE core_factoryqueueitem (
                id INTEGER PRIMARY KEY, key TEXT, kind TEXT);
              CREATE TABLE core_discoverysnapshot (
                id INTEGER PRIMARY KEY, hypothesis_id INTEGER, url TEXT,
                content_hash TEXT, retrieved_at TEXT, record TEXT);
            """)
            conn.executemany("INSERT INTO core_factoryqueueitem VALUES (?,?,?)", [
                (1, "discovery:ASTRA-H001", "discovery"),
                (2, "discovery:ASTRA-H002", "discovery"),
                (3, "not-discovery", "run"),
            ])
            rows = [
                (1,1,"https://example.com/problem",hash_for("problem"),
                 "2026-10-14T00:00:00+00:00",json.dumps({"claim_type": "problem"})),
                (2,1,"https://example.org/buyer",hash_for("buyer"),
                 "2026-10-14T00:00:00+00:00",
                 json.dumps({"claim_type": "willingness_to_pay"})),
                (3,2,"https://example.net/unrelated",hash_for("other"),
                 "2026-10-14T00:00:00+00:00",
                 json.dumps({"claim_type": "willingness_to_pay"})),
                (4,3,"https://example.edu/wrong-kind",hash_for("wrong"),
                 "2026-10-14T00:00:00+00:00",
                 json.dumps({"claim_type": "willingness_to_pay"})),
                (5,1,"https://example.info/unclassified",hash_for("unclass"),
                 "2026-10-14T00:00:00+00:00",
                 json.dumps({"page_excerpt": "not classified"})),
            ]
            conn.executemany(
                "INSERT INTO core_discoverysnapshot VALUES (?,?,?,?,?,?)", rows)
        report = adapter.evaluate_db(self.db, [
            item("orchard", astra_queue_key="discovery:ASTRA-H001")], NOW)
        row = report["candidates"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertEqual(row["distinct_source_domains_preliminary"], 2)
        self.assertFalse(row["evidence_verified_independently"])
        self.assertFalse(row["build_authorized"])
        self.assertFalse(row["publish_authorized"])
        self.assertEqual(report["bridge_audit"]["astra_snapshots_examined"], 3)
        self.assertEqual(report["bridge_audit"]["astra_snapshots_eligible"], 2)

    def test_misleading_claim_does_not_make_buildable(self):
        with sqlite3.connect(self.db) as conn:
            conn.executescript("""
              CREATE TABLE core_factoryqueueitem (id INTEGER PRIMARY KEY, key TEXT, kind TEXT);
              CREATE TABLE core_discoverysnapshot (
                  id INTEGER PRIMARY KEY, hypothesis_id INTEGER, url TEXT,
                  content_hash TEXT, retrieved_at TEXT, record TEXT);
            """)
            conn.execute("INSERT INTO core_factoryqueueitem VALUES (1,'x','discovery')")
            for i, (host, typ) in enumerate([
                ("a.example.com", "problem"), ("b.example.org", "willingness_to_pay")
            ], 1):
                conn.execute("INSERT INTO core_discoverysnapshot VALUES (?,?,?,?,?,?)",
                             (i,1,f"https://{host}/test",hash_for(host),NOW,
                              json.dumps({"claim_type":typ, "claim": "fake sales"})))
        report = adapter.evaluate_db(self.db, [item("x", astra_queue_key="x")], NOW)
        self.assertEqual(report["candidates"][0]["status"], "REVIEW_REQUIRED")
        self.assertFalse(report["candidates"][0]["build_authorized"])
        self.assertFalse(report["candidates"][0]["payment_authorized"])

    def test_invalid_mapping_and_duplicate_rejected(self):
        for value in (True, -1, "1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "product_id"):
                    adapter.evaluate_db(self.db,[item("bad", product_id=value)],NOW)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            adapter.evaluate_db(self.db,[item("same"),item("same")],NOW)

    def test_missing_schema_reports_research_not_fake_success(self):
        empty = self.home / "empty.sqlite3"
        with sqlite3.connect(empty): pass
        result = adapter.evaluate_db(empty, [
            item("orchard", product_id=1, astra_queue_key="discovery:ASTRA-H001")
        ], NOW)
        self.assertFalse(result["bridge_audit"]["legacy_schema_available"])
        self.assertFalse(result["bridge_audit"]["astra_0049_schema_available"])
        self.assertEqual(result["candidates"][0]["status"], "RESEARCH_REQUIRED")

    def test_cli_creates_private_review_without_db_changes(self):
        source = self.home / "candidate.json"
        out = self.home / "result.json"
        source.write_text(json.dumps({"candidates":[item("orchard", product_id=1)]}),
                          encoding="utf-8")
        original = self.db.read_bytes()
        proc = subprocess.run([
            sys.executable, str(SCRIPT), "--db",str(self.db),
            "--candidates",str(source), "--out",str(out), "--now-utc",NOW,
        ],capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(self.db.read_bytes(),original)
        self.assertEqual(out.stat().st_mode & 0o777,0o600)
        self.assertIn("ASTRA_EVIDENCE_BRIDGE_READ_ONLY=true",proc.stdout)
        self.assertEqual(json.loads(out.read_text())["new_products_built"],0)

    def test_cli_does_not_overwrite_db_or_input(self):
        source=self.home/"c.json"
        source.write_text(json.dumps({"candidates":[]}))
        for target in (self.db,source):
            proc=subprocess.run([
              sys.executable,str(SCRIPT),"--db",str(self.db),
              "--candidates",str(source),"--out",str(target),
              "--now-utc",NOW],capture_output=True,text=True,timeout=10)
            self.assertNotEqual(proc.returncode,0)

if __name__=="__main__":
    unittest.main()
