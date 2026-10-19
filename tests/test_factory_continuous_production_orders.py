"""Acceptance tests: genuine factory instructions, never bogus goods or website calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"factory_continuous_production_orders.py"
spec=importlib.util.spec_from_file_location("factory_order_generator",str(SCRIPT))
orders=importlib.util.module_from_spec(spec)
spec.loader.exec_module(orders)

def base_entry(ident, blockers):
    return {"product_id":ident,
            "sha256":("%064x"%ident),
            "research_quality_gate":{
                "schema":"saeit.factory.research-readiness.v1",
                "blockers":blockers,
                "research_gate_passed":not blockers}}

class ProductionOrderGeneratorTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.rd=self.root/"research-dossiers"
        self.rd.mkdir()
    def seed(self, entries):
        (self.rd/"autonomous-portfolio.json").write_text(json.dumps({"entries":entries}))
    def get(self):
        folder=self.root/"production-instructions"
        status=json.loads((folder/"order-status.json").read_text())
        records=[json.loads(p.read_text()) for p in sorted((folder/"orders").glob("*.json"))]
        return status,records
    def test_one_unique_instruction_per_tick_without_products(self):
        self.seed([base_entry(1,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"])])
        for n in range(1,6):
            state=orders.generate(self.root)
            self.assertEqual(state["action"],"issued")
            self.assertEqual(state["pending"],n)
            self.assertEqual(state["id"],"WO-"+str(n).zfill(8))
        state=orders.generate(self.root)
        self.assertEqual(state["action"],"no_new_meaningful_input")
        report,records=self.get()
        self.assertEqual(len(records),5)
        self.assertEqual(len({x["fingerprint"] for x in records}),5)
        self.assertEqual(report["instructions_issued_total"],5)
        self.assertTrue(all(x["manufacturing_qa_passed"] is False for x in records))
        self.assertTrue(all(x["public_distribution_allowed"] is False for x in records))
        self.assertFalse((self.root/"production-warehouse").exists())
    def test_25_products_can_generate_unique_continuous_work(self):
        self.seed([base_entry(i,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED",
                                  "TEN_FACTOR_VALIDATION_PASS_REQUIRED"])
                   for i in range(1,26)])
        for n in range(1,61):
            r=orders.generate(self.root,max_backlog=100)
            self.assertEqual(r["action"],"issued")
            self.assertEqual(r["pending"],n)
        self.assertEqual(len(self.get()[1]),60)
        self.assertEqual(len({x["source_product_id"] for x in self.get()[1]}),4)
    def test_cap_prevents_unbounded_task_spam(self):
        self.seed([base_entry(1,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"])])
        self.assertEqual(orders.generate(self.root,2)["action"],"issued")
        self.assertEqual(orders.generate(self.root,2)["action"],"issued")
        self.assertEqual(orders.generate(self.root,2)["action"],"capacity_hold")
        self.assertEqual(len(self.get()[1]),2)
    def test_resuming_after_verified_completion(self):
        self.seed([base_entry(10,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"])])
        orders.generate(self.root,1)
        p=self.root/"production-instructions"/"orders"/"WO-00000001.json"
        entry=json.loads(p.read_text())
        entry["status"]="completed_verified"
        orders.atomic_json(p,entry)
        state=orders.generate(self.root,1)
        self.assertEqual(state["action"],"issued")
        self.assertEqual(state["pending"],1)
        self.assertEqual(len(self.get()[1]),2)
    def test_four_offline_channels_do_not_need_live_sites(self):
        self.seed([])
        inp=self.root/"production-order-inputs"
        inp.mkdir()
        for i,kind in enumerate(orders.SOURCES):
            (inp/(kind+".json")).write_text(json.dumps({
                "schema":orders.SCHEMA,
                "items":[{"id":"offline_"+str(i),"title":"Valid local instruction "+str(i),
                          "specification":"Design a complete testable offline prototype with exact unit tests.",
                          "family_id":"F28","specialty":"greenhouse-water",
                          "target_audience":"engineers","problem_solved":"water "+str(i),
                          "level":"advanced","language":"en"}]
            }))
        for i in range(4):
            r=orders.generate(self.root)
            self.assertEqual(r["action"],"issued")
        self.assertEqual({x["origin"] for x in self.get()[1]},set(orders.SOURCES))
        self.assertTrue(all(x["independent_of_websites"] for x in self.get()[1]))
    def test_no_source_is_reported_truthfully(self):
        self.seed([])
        self.assertEqual(orders.generate(self.root)["action"],"no_new_meaningful_input")
        self.assertEqual(self.get()[0]["instructions_issued_total"],0)
    def test_unverified_input_does_not_become_order(self):
        self.seed([])
        folder=self.root/"production-order-inputs"
        folder.mkdir()
        (folder/"customer-intake-snapshot.json").write_text(json.dumps({
            "schema":orders.SCHEMA,"items":[{"id":"x","title":"Fake","specification":"Short"}]}))
        with self.assertRaises(RuntimeError):
            orders.generate(self.root)
        self.assertEqual(list((self.root/"production-instructions"/"orders").iterdir()),[])
    def test_duplicate_offline_concept_is_not_a_new_product(self):
        self.seed([])
        path=self.root/"production-order-inputs"
        path.mkdir()
        items=[]
        for i in range(2):
            items.append({
                "id":"idea"+str(i)+"123","title":"Distinct color variant "+str(i),
                "specification":"Build functional greenhouse budget validator with real tests.",
                "family_id":"F28","specialty":"Greenhouse Water",
                "target_audience":"Managers","problem_solved":"Water Budget",
                "level":"Advanced","language":"en"})
        (path/"factory-invention-snapshot.json").write_text(json.dumps({
            "schema":orders.SCHEMA,"items":items}))
        self.assertEqual(orders.generate(self.root)["action"],"issued")
        self.assertEqual(orders.generate(self.root)["action"],"no_new_meaningful_input")
        self.assertEqual(len(self.get()[1]),1)

    def test_incomplete_family_identity_cannot_issue_order(self):
        self.seed([])
        path=self.root/"production-order-inputs"
        path.mkdir()
        (path/"market-research-snapshot.json").write_text(json.dumps({
            "schema":orders.SCHEMA,
            "items":[{"id":"market_01","title":"Real market topic",
                      "specification":"Build a testable solution with measurable outcomes."}]}))
        with self.assertRaisesRegex(RuntimeError,"FAMILY_ID_REQUIRED"):
            orders.generate(self.root)
        self.assertEqual(len(list((self.root/"production-instructions"/"orders").iterdir())),0)

    def test_invention_without_qa_is_not_product_release(self):
        self.seed([base_entry(17,[])])
        orders.generate(self.root)
        rec=self.get()[1][0]
        self.assertEqual(rec["phase"],"engineering")
        self.assertFalse(rec["technical_product_release"])
        self.assertFalse(rec["warehouse_goods_created"])
        self.assertIn("testable prototype",rec["subject"])

if __name__=="__main__":unittest.main()
