"""Synthetic, read-only backlog coverage; never touches real factory or owner data."""
import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_stage45_research_backlog.py"
spec = importlib.util.spec_from_file_location("astra_backlog_tests", SCRIPT)
backlog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backlog)
NOW = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)


class ResearchBacklogTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.db = self.root / "stage45-disposable.sqlite3"
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE django_migrations (app TEXT,name TEXT);
                INSERT INTO django_migrations VALUES
                    ('core','0049_astra_stage45_research_queue');
                CREATE TABLE core_factoryqueueitem (
                    id INTEGER PRIMARY KEY,key TEXT,kind TEXT,status TEXT,
                    priority_score NUMERIC,build_authorized INTEGER,
                    publish_authorized INTEGER,payment_authorized INTEGER,
                    evidence_verified_independently INTEGER);
                CREATE TABLE core_discoverysnapshot (
                    id INTEGER PRIMARY KEY,hypothesis_id INTEGER,url TEXT,
                    content_hash TEXT,retrieved_at TEXT,record TEXT);
                INSERT INTO core_factoryqueueitem VALUES
                   (1,'candidate_one','discovery','RESEARCH_REQUIRED',80,0,0,0,0),
                   (2,'candidate_two','discovery','RESEARCH_REQUIRED',NULL,0,0,0,0),
                   (3,'non_discovery','internal','RESEARCH_REQUIRED',NULL,0,0,0,0);
            """)

    def add_ref(self, topic, host, claim, n, when=None, illustrative=False):
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT INTO core_discoverysnapshot "
                "(hypothesis_id,url,content_hash,retrieved_at,record) VALUES (?,?,?,?,?)",
                (topic,"https://" + host + "/synthetic/" + str(n),
                 hashlib.sha256(str(n).encode()).hexdigest(),
                 (when or NOW).strftime("%Y-%m-%d %H:%M:%S.%f"),
                 json.dumps({"claim_type":claim,"illustrative_only":illustrative})))

    def report(self):
        return backlog.analyze(self.db,NOW.isoformat())

    def test_four_claims_only_create_research_actions_not_sale_authority(self):
        for i,(host,claim) in enumerate((
            ("example.com","problem"),("example.org","willingness_to_pay"),
            ("example.net","comparison"),("example.com","feasibility")),1):
            self.add_ref(1,host,claim,i)
        d=self.report()
        first=next(x for x in d["backlog"] if x["key"]=="candidate_one")
        second=next(x for x in d["backlog"] if x["key"]=="candidate_two")
        self.assertEqual(first["preliminary_unique_references"],4)
        self.assertEqual(first["preliminary_distinct_hosts"],3)
        self.assertEqual(first["missing_claims"],[])
        self.assertIn("BUILD_100_ITEM_INDEPENDENTLY_CHECKED_EVIDENCE_DOSSIER",
                      first["next_research_actions"])
        self.assertEqual(first["evidence_target"],100)
        self.assertEqual(first["commercial_quality_score"],None)
        self.assertFalse(first["build_authorized"])
        self.assertFalse(first["payment_authorized"])
        self.assertEqual(second["preliminary_unique_references"],0)
        self.assertEqual(len(second["missing_claims"]),4)
        self.assertEqual(d["verified_market_demand_topics"],0)
        self.assertEqual(d["commercially_released_products"],0)

    def test_unrelated_and_illustrative_sources_never_cross_pollinate(self):
        self.add_ref(2,"example.net","willingness_to_pay",1)
        self.add_ref(1,"example.org","problem",2,illustrative=True)
        d=self.report()
        rows={r["key"]:r for r in d["backlog"]}
        self.assertEqual(rows["candidate_one"]["preliminary_unique_references"],0)
        self.assertEqual(rows["candidate_two"]["preliminary_claims"],["willingness_to_pay"])
        self.assertEqual(d["invalid_or_unusable_snapshots"],1)

    def test_bad_timestamp_and_fake_ip_links_are_excluded(self):
        self.add_ref(1,"example.com","problem",1,when=NOW-timedelta(days=121))
        self.add_ref(1,"example.net","comparison",2,when=NOW+timedelta(days=1))
        self.add_ref(1,"127.0.0.1","feasibility",3)
        d=self.report()
        self.assertEqual(d["invalid_or_unusable_snapshots"],3)
        self.assertEqual(d["backlog"][0]["preliminary_unique_references"],0)

    def test_unauthorized_flag_fails_closed(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE core_factoryqueueitem SET publish_authorized=1 WHERE id=1")
        with self.assertRaisesRegex(ValueError,"authorization invariant"):
            self.report()

    def test_schema_and_marker_are_required(self):
        with sqlite3.connect(self.db) as c:
            c.execute("DELETE FROM django_migrations")
        with self.assertRaisesRegex(ValueError,"0049 migration"):
            self.report()

    def test_read_only_source_and_cli_output_permissions(self):
        before=hashlib.sha256(self.db.read_bytes()).digest()
        out=self.root/"private-report.json"
        r=subprocess.run(
            [sys.executable,str(SCRIPT),"--db",str(self.db),
             "--output",str(out),"--now-utc",NOW.isoformat()],
            text=True,capture_output=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("ASTRA_STAGE45_PRIVATE_BACKLOG_TOPICS=2",r.stdout)
        doc=json.loads(out.read_text())
        self.assertEqual(doc["factory_mutations"],0)
        self.assertEqual(doc["payment_attempts"],0)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).digest(),before)
        self.assertEqual(out.stat().st_mode & 0o777,0o600)
        with self.assertRaisesRegex(ValueError,"overwriting database"):
            backlog.main(["--db",str(self.db),"--output",str(self.db),
                          "--now-utc",NOW.isoformat()])

    def test_symlink_source_and_oversized_queue_are_denied(self):
        fake=self.root/"alias.sqlite3"
        fake.symlink_to(self.db)
        with self.assertRaisesRegex(ValueError,"symlinked"):
            backlog.analyze(fake,NOW.isoformat())
        with sqlite3.connect(self.db) as c:
            c.executemany(
                "INSERT INTO core_factoryqueueitem VALUES (?,?,?,?,?,?,?,?,?)",
                [(i,"topic"+str(i),"discovery","RESEARCH_REQUIRED",None,0,0,0,0)
                 for i in range(4,2005)])
        with self.assertRaisesRegex(ValueError,"outside bounded"):
            self.report()


if __name__=="__main__":
    unittest.main()
