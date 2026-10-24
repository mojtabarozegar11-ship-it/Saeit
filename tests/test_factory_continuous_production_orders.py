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
    def test_pending_argument_cannot_cap_valid_work(self):
        self.seed([base_entry(1,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"])])
        for _ in range(5):
            self.assertEqual(orders.generate(self.root,max_backlog=1)["action"],"issued")
        self.assertEqual(orders.generate(self.root,max_backlog=1)["action"],"no_new_meaningful_input")
        self.assertEqual(len(self.get()[1]),5)
        self.assertTrue(self.get()[0]["unbounded_intake"])
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
    def test_work_order_serial_expands_past_eight_digits(self):
        self.seed([base_entry(9,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"])])
        queue=self.root/"production-instructions"/"orders"
        queue.mkdir(parents=True)
        ident="WO-99999999"
        old={"schema":orders.SCHEMA,"id":ident,"status":"completed_verified",
             "fingerprint":"%064x"%99999999,"public_distribution_allowed":False}
        orders.atomic_json(queue/(ident+".json"),old)
        state=orders.generate(self.root)
        self.assertEqual(state["id"],"WO-100000000")
        self.assertEqual(len(self.get()[1]),2)

    def test_four_offline_channels_do_not_need_live_sites(self):
        self.seed([])
        inp=self.root/"production-order-inputs"
        inp.mkdir()
        for i,kind in enumerate(orders.SOURCES):
            (inp/(kind+".json")).write_text(json.dumps({
                "schema":orders.SCHEMA,
                "items":[{"id":"offline_"+str(i),"title":"Valid local instruction "+str(i),
                          "specification":"Design a complete testable offline prototype with exact unit tests."}]
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
    def test_invention_without_qa_is_not_product_release(self):
        self.seed([base_entry(17,[])])
        orders.generate(self.root)
        rec=self.get()[1][0]
        self.assertEqual(rec["phase"],"engineering")
        self.assertFalse(rec["technical_product_release"])
        self.assertFalse(rec["warehouse_goods_created"])
        self.assertIn("testable prototype",rec["subject"])

    def test_300_blocked_research_tasks_never_starve_real_specification(self):
        self.seed([base_entry(1,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"])])
        source=self.root/"production-order-inputs"
        source.mkdir()
        (source/"factory-invention-snapshot.json").write_text(json.dumps({
            "schema":orders.SCHEMA,"items":[{
                "id":"factory_lab_20261019","title":"Verified offline blueprint request",
                "specification":"Create a mathematical prototype with deterministic functional tests and source provenance."
            }]}))
        queue=self.root/"production-instructions"/"orders"
        queue.mkdir(parents=True)
        old_hashes={}
        for n in range(1,301):
            ident="WO-"+str(n).zfill(8)
            item={"schema":orders.SCHEMA,"id":ident,"status":"issued",
                  "fingerprint":"%064x"%n,"public_distribution_allowed":False,
                  "origin":"local-factory-research","phase":"research_rework",
                  "blocker":"FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"}
            orders.atomic_json(queue/(ident+".json"),item)
            old_hashes[ident]=orders.checksum(item)
        status=orders.generate(self.root)
        self.assertEqual(status["action"],"issued")
        self.assertEqual(status["id"],"WO-00000301")
        report,entries=self.get()
        self.assertEqual(len(entries),301)
        self.assertEqual(report["pending_research_instructions"],300)
        self.assertEqual(report["pending_manufacturing_instructions"],1)
        self.assertIsNone(report["research_capacity_available"])
        self.assertIsNone(report["manufacturing_capacity_available"])
        self.assertEqual(entries[-1]["phase"],"engineering_specification")
        self.assertFalse(entries[-1]["publication_approved"])
        for order_id,digest in old_hashes.items():
            self.assertEqual(orders.checksum(json.loads((queue/(order_id+".json")).read_text())),digest)
        self.assertEqual(orders.generate(self.root)["action"],"issued")
        self.assertEqual(len(self.get()[1]),302)

    def test_legacy_limit_argument_does_not_cap_queue_or_bypass_qa(self):
        self.seed([base_entry(1,["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"])])
        for _ in range(5):
            self.assertEqual(orders.generate(self.root,max_backlog=1)["action"],"issued")
        report,records=self.get()
        self.assertEqual(report["pending_research_instructions"],5)
        self.assertEqual(report["pending_manufacturing_instructions"],0)
        self.assertIsNone(report["research_capacity_available"])
        self.assertFalse(report["distribution_enabled"])
        self.assertTrue(all(x["public_distribution_allowed"] is False for x in records))

if __name__=="__main__":unittest.main()
