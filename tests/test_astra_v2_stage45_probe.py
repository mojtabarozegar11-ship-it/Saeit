"""Synthetic read-only stage4/5 adapter diagnostics regression suite."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"astra_v2_stage45_probe.py"
spec=importlib.util.spec_from_file_location("astra_stage45_probe",SCRIPT)
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Stage45ProbeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.old=self.root/"legacy.sqlite3"
        self.v2=self.root/"private.sqlite3"
        with sqlite3.connect(self.old) as conn:
            conn.executescript("""
                CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT, name TEXT);
                INSERT INTO django_migrations VALUES (1,'core','0039_educationassessment');
                CREATE TABLE core_product (id INTEGER PRIMARY KEY, factory_managed INTEGER, active INTEGER);
                CREATE TABLE core_factoryrun (id INTEGER PRIMARY KEY, product_id INTEGER);
                CREATE TABLE core_researchproject (id INTEGER PRIMARY KEY, factory_run_id INTEGER);
                CREATE TABLE core_researchsource (id INTEGER PRIMARY KEY, project_id INTEGER,
                                                 url TEXT,content_hash TEXT);
                CREATE TABLE core_evidence (id INTEGER PRIMARY KEY,source_id INTEGER,project_id INTEGER);
                INSERT INTO core_product VALUES (1,1,0),(2,1,1),(3,0,0);
                INSERT INTO core_factoryrun VALUES (1,1);
                INSERT INTO core_researchproject VALUES (1,1);
                INSERT INTO core_researchsource VALUES
                  (1,1,'https://example.edu/d', 'this-is-not-reliable-evidence'),
                  (2,1,'https://example.org/p','not-necessarily-market-demand');
                INSERT INTO core_evidence VALUES (1,1,1);
            """)
        with sqlite3.connect(self.v2) as conn:
            conn.executescript("""
                CREATE TABLE jobs (id INTEGER PRIMARY KEY,builder TEXT,stage TEXT,artifact_sha TEXT);
                INSERT INTO jobs VALUES
                  (1,'orchard_decision_audit_v2','PRIVATE_QA_PASSED','a'),
                  (2,'orchard_decision_audit_v2','PRIVATE_QA_PASSED','b'),
                  (3,'farm_procurement_audit_v1','PRIVATE_QA_PASSED','c'),
                  (4,'farm_water_land_margin_audit_v1','PRIVATE_QA_PASSED','d'),
                  (5,'orchard_decision_audit_v2','QUEUED',NULL);
            """)

    def evaluate(self):
        return probe.analyze(self.old,self.v2)

    def test_no_stage45_migration_is_explicitly_blocked(self):
        report=self.evaluate()
        f=report["legacy_factory"]
        self.assertTrue(f["legacy_readonly_adapter_schema_compatible"])
        self.assertEqual(f["migration"]["latest_core_migration"],
                         "0039_educationassessment")
        self.assertFalse(f["migration"]["astra_0049_recorded"])
        self.assertFalse(f["stage45_schema_tables_present"])
        self.assertFalse(f["stage45_cutover_authorized"])
        self.assertFalse(report["bridge_in_place"])
        self.assertIn("RECONCILE_CODE_SCHEMA",report["next_gate"])

    def test_reference_counts_are_not_buyer_claims(self):
        data=self.evaluate()
        self.assertEqual(data["legacy_factory"]["aggregates"]["core_product"],3)
        self.assertEqual(data["legacy_factory"]["aggregates"]["private_factory_managed_drafts"],1)
        self.assertEqual(data["legacy_factory"]["aggregates"]["source_rows_linked_to_evidence"],1)
        self.assertFalse(data["legacy_factory"]["real_market_demand_independently_attested"])
        self.assertEqual(data["new_commercial_products_verified"],0)

    def test_exact_distinct_private_families_not_job_count(self):
        data=self.evaluate()
        self.assertEqual(data["isolated_astra_v2"]["families_qa_passed"],3)
        self.assertEqual(data["isolated_astra_v2"]["jobs_by_stage"]["PRIVATE_QA_PASSED"],4)
        self.assertEqual(data["isolated_astra_v2"]["jobs_by_stage"]["QUEUED"],1)

    def test_0049_tables_without_migration_still_blocked(self):
        with sqlite3.connect(self.old) as conn:
            conn.executescript("""
              CREATE TABLE core_factoryqueueitem (id INTEGER PRIMARY KEY,key TEXT,kind TEXT);
              CREATE TABLE core_discoverysnapshot (
                id INTEGER PRIMARY KEY,hypothesis_id INTEGER,url TEXT,
                content_hash TEXT,retrieved_at TEXT,record TEXT);
            """)
        result=self.evaluate()
        self.assertTrue(result["legacy_factory"]["stage45_schema_tables_present"])
        self.assertFalse(result["legacy_factory"]["migration"]["astra_0049_recorded"])
        self.assertIn("RECONCILE_CODE_SCHEMA",result["next_gate"])

    def test_migration_without_0049_tables_also_blocks(self):
        with sqlite3.connect(self.old) as conn:
            conn.execute("INSERT INTO django_migrations VALUES (2,'core','0049_astra_factory')")
        result=self.evaluate()
        self.assertTrue(result["legacy_factory"]["migration"]["astra_0049_recorded"])
        self.assertFalse(result["legacy_factory"]["stage45_schema_tables_present"])
        self.assertFalse(result["legacy_factory"]["stage45_cutover_authorized"])

    def test_schema_ready_only_means_review_next(self):
        with sqlite3.connect(self.old) as conn:
            conn.executescript("""
              CREATE TABLE core_factoryqueueitem (id INTEGER PRIMARY KEY,key TEXT,kind TEXT);
              CREATE TABLE core_discoverysnapshot (
                id INTEGER PRIMARY KEY,hypothesis_id INTEGER,url TEXT,
                content_hash TEXT,retrieved_at TEXT,record TEXT);
              INSERT INTO django_migrations VALUES (2,'core','0049_astra_factory');
            """)
        r=self.evaluate()
        self.assertEqual(r["next_gate"],
                         "VERIFY_CODE_AND_STAGING_MIGRATION_WITH_INDEPENDENT_TESTS")
        self.assertFalse(r["bridge_in_place"])
        self.assertFalse(r["legacy_factory"]["stage45_cutover_authorized"])

    def test_missing_columns_detected_without_sql_injection(self):
        with sqlite3.connect(self.old) as conn:
            conn.execute("DROP TABLE core_researchsource")
            conn.execute("CREATE TABLE core_researchsource (id INTEGER)")
        r=self.evaluate()
        self.assertFalse(r["legacy_factory"]["legacy_readonly_adapter_schema_compatible"])
        self.assertIn("project_id", r["legacy_factory"]["schema"]["legacy"]
                      ["core_researchsource"]["missing_required_columns"])
        self.assertIsNone(r["legacy_factory"]["aggregates"]["core_researchsource"])

    def test_source_and_private_db_same_path_forbidden(self):
        with self.assertRaisesRegex(ValueError,"independent"):
            probe.analyze(self.old,self.old)

    def test_symlinked_db_forbidden(self):
        link=self.root/"link.sqlite3"
        link.symlink_to(self.old)
        with self.assertRaisesRegex(ValueError,"symlink"):
            probe.analyze(link,self.v2)

    def test_db_contents_unchanged_by_probe(self):
        original=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.old,self.v2)]
        probe.analyze(self.old,self.v2)
        after=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.old,self.v2)]
        self.assertEqual(original,after)

    def test_cli_does_not_print_urls_or_personal_data(self):
        run=subprocess.run([sys.executable,str(SCRIPT),"--factory-db",str(self.old),
                            "--private-db",str(self.v2)],text=True,
                            capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        obj=json.loads(run.stdout)
        self.assertEqual(obj["site_mutations"],0)
        self.assertEqual(obj["factory_database_writes"],0)
        self.assertEqual(obj["private_database_writes"],0)
        self.assertNotIn("example.edu",run.stdout)
        self.assertNotIn("example.org",run.stdout)

if __name__ == "__main__":
    unittest.main()
