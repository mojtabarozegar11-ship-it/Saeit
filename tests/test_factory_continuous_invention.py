"""Acceptance: real private product artifacts, no fabricated demand or sales."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    s=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    obj=importlib.util.module_from_spec(s);s.loader.exec_module(obj);return obj

invent=module("factory_continuous_invention")
intake=module("factory_design_intake")
designer=module("factory_recipe_designer")
maker=module("factory_product_maker")

class ContinuousInventionTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)

    def test_two_independent_proposals_become_distinct_tested_real_products(self):
        first=invent.propose(self.root,max_new=2)
        self.assertEqual(first["new_technical_briefs_this_tick"],2)
        self.assertEqual(first["store_ready_products"],0)
        briefs=list((self.root/"engineering-briefs").glob("auto_need_*.json"))
        self.assertEqual(len(briefs),2)
        self.assertEqual(intake.cycle(self.root)["enqueued"],2)
        state=designer.cycle(self.root,max_designs=2)
        self.assertEqual(state["new_recipes"],2)
        verified=set()
        for entry in state["actions"]:
            recipe=entry["result"]["recipe"]
            result=maker.manufacture(recipe,self.root/"generated-product-recipes",self.root/"digital-products")
            self.assertEqual(result["qa_status"],"passed")
            self.assertTrue(result["changed"])
            manifest=json.loads((self.root/"digital-products"/recipe/"manufacturing_manifest.json").read_text())
            self.assertFalse(manifest["public_listing_enabled"])
            verified.add(entry["result"]["functional_sha256"])
        self.assertEqual(len(verified),2)
        self.assertEqual(invent.propose(self.root,max_new=1)["new_technical_briefs_this_tick"],1)
        self.assertEqual(len(list((self.root/"engineering-briefs").glob("*.json"))),3)

    def test_atomic_replay_and_legacy_backlog_hint_never_stalls_intake(self):
        first=invent.propose(self.root,max_new=2,max_pending=2)
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.root/"engineering-briefs").glob("*.json")}
        again=invent.propose(self.root,max_new=2,max_pending=2)
        self.assertEqual(first["new_technical_briefs_this_tick"],2)
        self.assertEqual(again["new_technical_briefs_this_tick"],2)
        self.assertEqual(again["pending_internal_design_briefs"],4)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (self.root/"engineering-briefs").glob("*.json")}
        self.assertEqual(len(after),4)
        self.assertTrue(set(before).issubset(after))
        self.assertEqual({k:after[k] for k in before},before)

    def test_does_not_spoof_market_evidence_or_commercial_approval(self):
        invent.propose(self.root,max_new=1)
        p=next((self.root/"engineering-briefs").glob("*.json"))
        record=json.loads(p.read_text())
        self.assertEqual(record["origin"],"factory_invention")
        self.assertFalse(record["commercial_release"])
        self.assertFalse(record["marketing_or_research_verified"])
        evidence=self.root/record["evidence"][0]["path"]
        self.assertEqual(hashlib.sha256(evidence.read_bytes()).hexdigest(),record["evidence"][0]["sha256"])
        self.assertIn("No evidence of customer demand",evidence.read_text())
        self.assertEqual(intake.cycle(self.root)["enqueued"],1)
        evidence.write_text("altered")
        # Same proposal is never silently rewritten after evidence corruption.
        self.assertEqual(invent.propose(self.root,max_pending=1)["total_issued_briefs"],1)

    def test_extension_pack_rejects_invalid_schema_and_accepts_real_need(self):
        folder=self.root/"invention-pattern-packs";folder.mkdir()
        p=folder/"research.json"
        p.write_text(json.dumps({"schema":invent.SCHEMA,"patterns":[{
            "id":"quality_ratio","title":"Independent laboratory quality ratio",
            "problem":"Calculate verified test pass ratio from counted laboratory passes and tests.",
            "expression":"passing_tests / total_tests","output_unit":"ratio","family_id":"F28",
            "inputs":[{"name":"passing_tests","unit":"tests"},{"name":"total_tests","unit":"tests"}]
        }]}))
        ids=[x[0] for x in invent.patterns(self.root)]
        self.assertIn("quality_ratio",ids)
        self.assertGreater(len(ids),len(invent.BUILTIN))
        data=json.loads(p.read_text());data["patterns"][0]["expression"]="__import__('os').system('echo bad')"
        p.write_text(json.dumps(data))
        # An unsafe operator never becomes an executable brief.
        for j in range(4):
            result=invent.propose(self.root,max_new=5,max_pending=50)
        self.assertTrue(all("auto_need_quality_ratio.json"!=x.name
                        for x in (self.root/"engineering-briefs").iterdir()))
        self.assertTrue(any(v["id"]=="auto_need_quality_ratio" for v in result["blocked_patterns"]))

    def test_duplicate_pattern_units_and_math_not_new_product(self):
        folder=self.root/"invention-pattern-packs";folder.mkdir()
        (folder/"duplicate.json").write_text(json.dumps({"schema":invent.SCHEMA,"patterns":[{
            "id":"renamed_trip_time","title":"Cosmetically renamed journey planner",
            "problem":"A duplicate formula with renamed inputs is not a new functional need.",
            "expression":"measured_distance / measured_speed","output_unit":"hours","family_id":"F28",
            "inputs":[{"name":"measured_distance","unit":"km"},{"name":"measured_speed","unit":"km/hour"}]
        }]}))
        # Scan through the finite built-ins, then reach the extension pack.
        for _ in range(4):
            result=invent.propose(self.root,max_new=5,max_pending=30)
        self.assertGreaterEqual(result["duplicate_pattern_skips"],1)
        self.assertFalse((self.root/"engineering-briefs/auto_need_renamed_trip_time.json").exists())

if __name__=="__main__":unittest.main()
