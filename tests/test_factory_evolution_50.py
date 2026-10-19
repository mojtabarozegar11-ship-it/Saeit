"""50 evolution generations are candidate protocols, never fake upgraded code."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/"scripts/factory_evolution_50.py"
spec=importlib.util.spec_from_file_location("safe_genetic_evolution",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FactoryEvolution50Tests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        for name,data in (
          ("production-family-management/family-dashboard.json",{
            "schema":"saeit.factory.family-master-dashboard.v1","registered_families":40,
            "fully_verified_active_producer_families":0,
            "max_total_simultaneous_jobs_authorized":0,"distribution_enabled":False,
            "unassigned_work_orders":{"missing_passports":66}}),
          ("product-lifecycle/dashboard.json",{
            "schema":"saeit.factory.lifecycle.v1","site_distribution_enabled":False,
            "final_commercially_verified_stock":0,"open_defects":0,
            "manufacturing_order_automation_complete":False}),
          ("production-warehouse/stock-register.json",{
            "distribution_enabled":False,"finished_goods_versions":2}),
          ("production-instructions/order-status.json",{
            "instructions_issued_total":66,"pending_instructions":66}),
          ):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(data))
    def test_exactly_fifty_distinct_genetic_blueprints_not_fake_upgrades(self):
        profiles=[m.genotype(i) for i in range(1,51)]
        self.assertEqual(len(profiles),50)
        self.assertEqual(len({(x["gene"],x["benchmark_phase"]) for x in profiles}),50)
        self.assertEqual(len({x["gene"] for x in profiles}),10)
        self.assertTrue(all(m.safe_strategy(x["proposed_policy"]) for x in profiles))
        self.assertTrue(all(x["automatic_upgrade_allowed"] is False for x in profiles))
        self.assertTrue(all(x["requires_independent_signed_approval"] for x in profiles))
        for n in (-1,0,51,False):
            with self.assertRaises(RuntimeError):m.genotype(n)
    def test_first_tick_proposes_once_without_pretending_progress(self):
        one=m.tick(self.root)
        self.assertEqual(one["verified_promoted_generation"],0)
        self.assertEqual(one["pending_candidate"],1)
        self.assertEqual(one["approved_code_upgrades"],0)
        self.assertFalse(one["production_adapter_modified"])
        self.assertEqual(one["last_metrics"]["approved_final_stock"],0)
        self.assertEqual(one["last_metrics"]["technical_qa_stock_not_final"],2)
        self.assertIsNone(one["last_metrics"]["real_quality_gated_builds_this_tick"])
        doc=m.read_json(self.root/"factory-evolution-50/generation-01-proposed.json")
        self.assertFalse(doc["promoted"])
        self.assertFalse(doc["real_benchmark_passed"])
        self.assertFalse(doc["human_review_recorded"])
        again=m.tick(self.root)
        self.assertEqual(again["verified_promoted_generation"],0)
        self.assertEqual(again["pending_candidate"],1)
        self.assertEqual(len(list((self.root/"factory-evolution-50").glob("generation-*-proposed.json"))),1)
    def test_distribution_fails_closed(self):
        path=self.root/"production-family-management/family-dashboard.json"
        data=json.loads(path.read_text());data["distribution_enabled"]=True
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError,"EVOLUTION_SITE_DISTRIBUTION_NOT_DISABLED"):
            m.tick(self.root)
        self.assertFalse((self.root/"factory-evolution-50").exists())
    def test_status_immutable_safety_flags(self):
        m.tick(self.root)
        p=self.root/"factory-evolution-50/evolution-status.json"
        bad=json.loads(p.read_text());bad["distribution_enabled"]=True
        p.write_text(json.dumps(bad))
        with self.assertRaisesRegex(RuntimeError,"EVOLUTION_PREVIOUS_STATE_INVALID"):
            m.tick(self.root)
    def test_invalid_blueprint_does_not_authorize_dispatch(self):
        profile=m.genotype(50)
        policy=profile["proposed_policy"]
        policy["max_new_workers"]=2
        self.assertFalse(m.safe_strategy(policy))
        self.assertFalse(profile["automatic_upgrade_allowed"])

if __name__=="__main__":unittest.main()
