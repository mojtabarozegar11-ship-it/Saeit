"""Stage 1 must finish its own validation regardless of stage 2 backlog."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

STAGE = load("stage1_handoff", "scripts/factory_stage1_handoff.py")
GEN = load("continuous_orders_for_stage1", "scripts/factory_continuous_production_orders.py")
AGRI = load("agri_p0_for_stage1", "scripts/factory_agri200_p0_intake.py")
CATALOG = BASE / "docs/agri200_p0_catalog.tsv"


class IndependentStageOneTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "research-dossiers").mkdir()
        (self.root / "research-dossiers" / "autonomous-portfolio.json").write_text(
            json.dumps({"entries": []}))
        self.orders = self.root / "production-instructions" / "orders"

    def input_order(self, ident="WO-00000001", priority=False):
        obj = {
            "schema": GEN.SCHEMA, "id": ident,
            "status": "issued", "origin": "local-factory-research",
            "phase": "research_rework", "priority": "P1",
            "source_sha256": "a"*64, "fingerprint": "b"*64,
            "subject": "Research verifiable field data",
            "instruction": "Document independent source evidence and a reproducible procedure.",
            "acceptance": ["Dated traceable source receipt"],
            "manufacturing_qa_passed": False, "publication_approved": False,
            "public_distribution_allowed": False
        }
        if priority:
            obj.update(origin="owner_requested_agri200_p0", priority="P0", priority_rank=1)
        GEN.atomic_json(self.orders / (ident + ".json"), obj)
        return obj

    def test_order_ids_expand_past_eight_digits(self):
        self.input_order("WO-100000000")
        stat = STAGE.run(self.root)
        self.assertEqual(stat["new_handoffs"], 1)
        self.assertTrue((self.root / "production-instructions/stage-02/inbox/WO-100000000--r001.json").is_file())

    def test_valid_order_handoff_no_research_qa_or_website(self):
        order = self.input_order()
        stat = STAGE.run(self.root)
        self.assertEqual(stat["new_handoffs"], 1)
        path = self.root / "production-instructions/stage-02/inbox/WO-00000001--r001.json"
        packet = json.loads(path.read_text())
        self.assertEqual(packet["stage_2_status"], "received_pending_processing")
        self.assertEqual(packet["work_order"], order)
        self.assertFalse(packet["quality1000_approved"])
        self.assertFalse(packet["public_distribution_allowed"])
        self.assertFalse((self.root / "production-warehouse").exists())
        self.assertEqual(STAGE.run(self.root)["new_handoffs"], 0)

    def test_invalid_input_blocked_without_forwarding(self):
        doc = self.input_order()
        doc["publication_approved"] = True
        GEN.atomic_json(self.orders / (doc["id"] + ".json"), doc)
        s = STAGE.run(self.root)
        self.assertEqual(s["blocked_items_this_run"], 1)
        self.assertEqual(list((self.root / "production-instructions/stage-02/inbox").glob("*.json")), [])
        self.assertTrue((self.root / "production-instructions/stage-01/blocked/WO-00000001--r001.json").exists())

    def test_stage_one_is_independent_of_existing_stage_two_queue(self):
        self.input_order()
        inbox = self.root / "production-instructions/stage-02/inbox"
        inbox.mkdir(parents=True)
        for n in range(1, 5):
            (inbox / ("old-%d.json" % n)).write_text('{"stage_2_status":"pending"}')
        self.assertEqual(STAGE.run(self.root)["new_handoffs"], 1)
        self.assertEqual(len(list(inbox.glob("*.json"))), 5)

    def test_p0_first_priority_and_two_hundred_real_receipts(self):
        AGRI.install(self.root, CATALOG)
        self.input_order("WO-00000201")
        s = STAGE.run(self.root, batch=200)
        self.assertEqual(s["new_handoffs"], 200)
        self.assertEqual(s["still_unscanned"], 1)
        inbox = self.root / "production-instructions/stage-02/inbox"
        self.assertEqual(len(list(inbox.glob("*.json"))), 200)
        self.assertFalse((inbox / "WO-00000201--r001.json").exists())
        self.assertEqual(STAGE.run(self.root)["new_handoffs"], 1)
        self.assertEqual(len(list(inbox.glob("*.json"))), 201)

    def test_returned_corrected_instruction_gets_new_revision(self):
        orig = self.input_order()
        STAGE.run(self.root)
        revised = dict(orig, instruction=orig["instruction"] + " Add provenance checks.")
        work = {
            "schema": STAGE.RETURN_SCHEMA, "order_id": orig["id"],
            "target_stage": 1, "source_stage": 2, "revision": 1000,
            "reason": "Missing provenance requirements",
            "corrected_work_order": revised
        }
        returns = self.root / "production-instructions/stage-01/return-inbox"
        GEN.atomic_json(returns / "correction.json", work)
        s = STAGE.run(self.root)
        self.assertEqual(s["returned_handoffs"], 1)
        self.assertTrue((self.root / "production-instructions/stage-02/inbox/WO-00000001--r1000.json").is_file())
        self.assertEqual(STAGE.run(self.root)["returned_handoffs"], 0)

    def test_unbounded_backlog_and_independent_stage1_handoff(self):
        entries = [{"product_id": 10, "sha256": "c"*64,
                    "research_quality_gate": {
                        "schema": "saeit.factory.research-readiness.v1",
                        "blockers": ["FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"],
                        "research_gate_passed": False}}]
        (self.root / "research-dossiers/autonomous-portfolio.json").write_text(
            json.dumps({"entries": entries}))
        self.assertEqual(GEN.generate(self.root, max_backlog=1)["action"], "issued")
        self.assertEqual(STAGE.run(self.root)["new_handoffs"], 1)
        resumed = GEN.generate(self.root, max_backlog=1)
        self.assertEqual(resumed["action"], "issued")
        report = json.loads((self.root / "production-instructions/order-status.json").read_text())
        self.assertEqual(report["pending_stage1_instructions"], 1)
        self.assertEqual(report["pending_downstream_or_rework_instructions"], 1)
        self.assertTrue(report["stage1_capacity_independent_of_stage2"])
        self.assertFalse(report["distribution_enabled"])

    def test_receipt_collision_never_overwrites_handoff(self):
        self.input_order()
        STAGE.run(self.root)
        path = self.root / "production-instructions/stage-02/inbox/WO-00000001--r001.json"
        original = json.loads(path.read_text())
        original["source_order_sha256"] = "0"*64
        GEN.atomic_json(path, original)
        self.assertEqual(STAGE.run(self.root)["blocked_items_this_run"], 1)
        self.assertEqual(json.loads(path.read_text())["source_order_sha256"], "0"*64)


if __name__ == "__main__":
    unittest.main()
