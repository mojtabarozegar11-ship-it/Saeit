"""Research plans are safe, small, transparent and must not claim real demand."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1]/"scripts/astra_v2_private_research_dossiers.py"
spec=importlib.util.spec_from_file_location("astra_research_plans",SRC)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PrivateResearchDossiersTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.legacy=root/"legacy.sqlite3"
        self.private=root/"private.sqlite3"
        self.out=root/"private-dossiers"
        self.out.mkdir(mode=0o700)
        with sqlite3.connect(self.legacy) as db:
            db.executescript("""
                CREATE TABLE core_researchproject (
                   id INTEGER PRIMARY KEY, factory_run_id INTEGER);
                CREATE TABLE core_factoryrun (
                   id INTEGER PRIMARY KEY, product_id INTEGER);
                CREATE TABLE core_researchsource (
                   id INTEGER PRIMARY KEY, project_id INTEGER,
                   url TEXT, content_hash TEXT, publisher TEXT, snapshot_hash TEXT);
                CREATE TABLE core_evidence (
                   id INTEGER PRIMARY KEY, project_id INTEGER,
                   source_id INTEGER);
                INSERT INTO core_factoryrun VALUES (10,1),(11,2);
                INSERT INTO core_researchproject VALUES (20,10),(21,11);
                INSERT INTO core_researchsource VALUES
                   (30,20,'https://extension.psu.edu/orchard', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','PSU', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
                   (31,20,'https://extension.psu.edu/orchard', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','PSU', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
                   (32,20,'https://mycwa.engg.ksu.edu/tool',NULL,'KSU',NULL),
                   (33,20,'http://127.0.0.1/private','bad','Untrusted',NULL),
                   (34,20,'https://user:token@example.edu/sensitive',NULL,'None',NULL),
                   (35,21,'https://example.com/other',NULL,'example',NULL);
                INSERT INTO core_evidence VALUES (40,20,30),(41,20,32);
            """)
        with sqlite3.connect(self.private) as db:
            db.executescript("""
                CREATE TABLE research_tasks(
                    legacy_product_id INTEGER PRIMARY KEY,
                    stage TEXT,
                    source_refs_unverified INTEGER,
                    market_demand_verified INTEGER DEFAULT 0,
                    sale_ready INTEGER DEFAULT 0,
                    quality_score INTEGER
                );
                INSERT INTO research_tasks VALUES
                    (1,'WAITING_FOR_EVIDENCE',6,0,0,NULL),
                    (2,'REVIEW_REQUIRED',1,0,0,NULL),
                    (3,'WAITING_FOR_EVIDENCE',0,0,0,NULL);
            """)

    def build(self, **kwargs):
        return mod.build(self.legacy,self.private,self.out,**kwargs)

    def test_plans_never_promote_synthetic_or_structural_sources(self):
        r=self.build()
        self.assertEqual(r["dossiers_written"],2)
        self.assertEqual(r["independently_verified_commercial_products"],0)
        self.assertEqual(r["network_requests"],0)
        entry=json.loads((self.out/"research-1.json").read_text())
        counts=entry["observed_source_statistics"]
        self.assertEqual(counts["source_rows_inspected_max500"],5)
        self.assertEqual(counts["structurally_attributed_unique_references_unverified"],2)
        self.assertEqual(counts["distinct_publisher_domains_unverified"],2)
        self.assertEqual(counts["linked_evidence_rows_unverified"],2)
        self.assertEqual(entry["research_evidence_target"],100)
        self.assertEqual(entry["independently_verified_research_items"],0)
        self.assertEqual(entry["remaining_independent_evidence_items"],100)
        self.assertFalse(entry["release_authorized"])
        self.assertIsNone(entry["commercial_quality_score"])
        self.assertFalse(entry["market_research_performed_by_this_run"])

    def test_five_external_one_internal_actions(self):
        self.build()
        item=json.loads((self.out/"research-1.json").read_text())
        self.assertEqual(item["external_actions_required"],5)
        self.assertEqual(item["internal_actions_required"],1)
        self.assertEqual(len(item["next_research_actions"]),6)
        self.assertEqual(sum(x["type"]=="external" for x in item["next_research_actions"]),5)

    def test_reviewed_candidates_not_overwritten(self):
        self.build()
        self.assertFalse((self.out/"research-2.json").exists())

    def test_repeat_does_not_grow_inventory(self):
        self.build()
        self.build()
        self.assertEqual(sorted(p.name for p in self.out.iterdir()),
                         ["research-1.json","research-3.json"])

    def test_dossier_does_not_contain_raw_url_or_private_content(self):
        self.build()
        text=(self.out/"research-1.json").read_text()
        self.assertNotIn("https://",text)
        self.assertNotIn("mycwa",text)
        self.assertNotIn("token",text)
        self.assertNotIn("127.0.0.1",text)

    def test_invalid_retail_flags_block_all_writes(self):
        with sqlite3.connect(self.private) as db:
            db.execute("UPDATE research_tasks SET market_demand_verified=1 WHERE legacy_product_id=2")
        with self.assertRaisesRegex(ValueError,"RETAIL_GATE_NOT_FAIL_CLOSED"):
            self.build()
        self.assertEqual(list(self.out.iterdir()),[])

    def test_bad_folder_permissions_fail_closed(self):
        os.chmod(self.out,0o755)
        with self.assertRaisesRegex(ValueError,"PRIVATE_OUTPUT_DIRECTORY_PERMISSIONS"):
            self.build()

    def test_symlinked_output_refused(self):
        alias=self.out.parent/"alias"
        alias.symlink_to(self.out,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,"PRIVATE_OUTPUT_DIRECTORY_UNSAFE"):
            mod.build(self.legacy,self.private,alias)

    def test_symlinked_json_refused(self):
        other=self.out.parent/"foreign.txt"
        other.write_text("secret")
        (self.out/"research-1.json").symlink_to(other)
        with self.assertRaisesRegex(ValueError,"DOSSIER_FILE_UNSAFE"):
            self.build()
        self.assertEqual(other.read_text(),"secret")

    def test_strict_batch_window(self):
        for limit in (0,51,-10):
            with self.subTest(limit=limit),self.assertRaisesRegex(ValueError,"BATCH_LIMIT_OUT_OF_RANGE"):
                self.build(limit=limit)

    def test_missing_legacy_schema_is_blocked(self):
        with sqlite3.connect(self.legacy) as db:
            db.execute("DROP TABLE core_evidence")
        with self.assertRaisesRegex(ValueError,"SCHEMA_MISSING_core_evidence"):
            self.build()


if __name__=="__main__":
    unittest.main()
