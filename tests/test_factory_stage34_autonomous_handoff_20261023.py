"""No-network gates for evidence-linked private stages three and four."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "factory_stage34_autonomous_handoff_20261023.py"
SPEC = importlib.util.spec_from_file_location("factory_stage34_private", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

class Stage34Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.area = self.root / "production-instructions"
        self.name = "WO-00000001--r001.json"
        sources = [{"id": "source%d" % i, "publisher": "Journal %d" % i,
                    "title": "Genuine bibliographic test source number %d" % i,
                    "url": "https://journal%d.example.org/works/%d" % (i, i)} for i in range(1, 5)]
        claims = [{"id": "claim%d" % i,
                   "statement": "Indexed research excerpt number %d about measured agricultural sampling constraints." % i,
                   "source_ids": ["source%d" % (i % 4 + 1)]}
                  for i in range(1, 6)]
        order = {"id": "WO-00000001", "source_product_id": "AGRI-001",
                 "editions": [
                     {"locale": "fa-IR", "title": "راهنمای کشت", "audience": "Iranian farmers"},
                     {"locale": "en-US", "title": "Crop handbook", "audience": "US learners"}]}
        origin = {"schema": mod.HANDOFF, "order_id": order["id"], "revision": 1,
                  "work_order": order, "quality1000_approved": False,
                  "public_distribution_allowed": False, "commercial_release": False}
        research = {
            "schema": mod.RESEARCH, "order_id": order["id"], "revision": 1,
            "source_product_id": "AGRI-001", "stage_1_handoff_sha256": mod.digest(origin),
            "stage2_documentation_complete": True, "independent_scientific_review": False,
            "manuscript_created": False,
            "sources": sources, "claims": claims,
            "locale_scopes": {
                "fa-IR": "Research conditions and limitations for Iranian audiences.",
                "en-US": "Research conditions and limitations for United States audiences."},
            "quality1000_approved": False, "public_distribution_allowed": False,
            "commercial_release": False
        }
        stage3_input = {
            "schema": mod.HANDOFF, "order_id": order["id"], "revision": 1,
            "previous_stage": 2, "next_stage": 3, "desk_research_file": self.name,
            "desk_research_sha256": mod.digest(research),
            "quality1000_approved": False, "public_distribution_allowed": False,
            "commercial_release": False}
        receipt = {
            "schema": mod.HANDOFF, "order_id": order["id"],
            "stage_2_completed": True, "research_sha256": mod.digest(research),
            "stage_3_packet_sha256": mod.digest(stage3_input)
        }
        self.put("stage-02/inbox", origin)
        self.put("stage-02/completed-dossiers", research)
        self.put("stage-02/receipts", receipt)
        self.put("stage-03/inbox", stage3_input)

    def put(self, stage_folder, obj):
        mod.atomic(self.area / stage_folder / self.name, obj)

    def change(self, stage_folder, callback):
        path = self.area / stage_folder / self.name
        obj = json.loads(path.read_text())
        callback(obj)
        mod.atomic(path, obj)

    def test_stage3_and_4_round_robin_do_not_starve_later_orders(self):
        for stage in (3, 4):
            mod.private_dir(self.area / ("stage-%02d" % stage))
            names = ["order-a", "order-b", "order-c"]
            seen = []
            for _ in range(6):
                selected, path, next_state = mod.fair_batch(self.area, stage, names, 1)
                seen.extend(selected)
                mod.atomic(path, next_state)
            self.assertEqual(seen, names + names)
            self.assertEqual(mod.read(path)["next_index"], 0)
            self.assertEqual(mod.fair_batch(self.area, stage, names, 10)[0], names)

    def test_corrupted_cursor_does_not_resume_unsafely(self):
        path = self.area / "stage-03/round-robin-cursor.json"
        mod.atomic(path, {"schema": "saeit.factory.stage3.round-robin.v1",
                          "next_index": "invalid"})
        with self.assertRaisesRegex(RuntimeError, "STAGE34_CURSOR_INVALID"):
            mod.fair_batch(self.area, 3, ["order-a"], 1)

    def test_both_stages_progress_with_real_evidence_and_no_public_claim(self):
        result = mod.execute(self.root)
        self.assertEqual((result["stage3_new"], result["stage4_new"]), (1, 1))
        self.assertEqual(result["stage5_inbox_total"], 1)
        self.assertFalse(result["websites_modified"])
        design = mod.read(self.area / "stage-03/completed-designs" / self.name)
        sample = mod.read(self.area / "stage-04/completed-prototypes" / self.name)
        self.assertEqual(set(design["edition_plans"]), {"fa-IR", "en-US"})
        self.assertEqual(len(sample["bilingual_sample_activities"]), 5)
        self.assertFalse(design["full_manuscript_created"])
        self.assertFalse(sample["commercial_release"])
        self.assertFalse(sample["quality1000_approved"])
        self.assertFalse(sample["independent_scientific_review"])
        self.assertEqual(mod.execute(self.root)["stage5_inbox_total"], 1)
        self.assertEqual(mod.execute(self.root)["stage3_new"], 0)

    def test_tampered_stage2_source_does_not_advance(self):
        self.change("stage-02/completed-dossiers",
                    lambda doc: doc["claims"][0].update({"statement": "Silent tamper"}))
        result = mod.execute(self.root)
        self.assertEqual(result["stage3_blocked_this_tick"], 1)
        self.assertEqual(result["stage5_inbox_total"], 0)
        self.assertFalse((self.area / "stage-04/inbox" / self.name).exists())

    def test_missing_bilingual_research_does_not_advance(self):
        def remove_fa(doc):
            doc["locale_scopes"].pop("fa-IR")
        self.change("stage-02/completed-dossiers", remove_fa)
        research = mod.read(self.area / "stage-02/completed-dossiers" / self.name)
        self.change("stage-03/inbox",
                    lambda doc: doc.update({"desk_research_sha256": mod.digest(research)}))
        stage3_packet = mod.read(self.area / "stage-03/inbox" / self.name)
        self.change("stage-02/receipts",
                    lambda doc: doc.update({"research_sha256": mod.digest(research),
                    "stage_3_packet_sha256": mod.digest(stage3_packet)}))
        self.assertEqual(mod.execute(self.root)["stage3_blocked_this_tick"], 1)

    def test_stage4_cannot_run_without_prior_receipt(self):
        self.put("stage-04/inbox", {"schema": mod.HANDOFF, "previous_stage": 3, "next_stage": 4})
        result = mod.execute(self.root)
        self.assertEqual(result["stage3_blocked_this_tick"], 1)
        self.assertEqual(result["stage4_blocked_this_tick"], 1)
        self.assertFalse((self.area / "stage-05/inbox" / self.name).exists())

    def test_no_source_claim_mapping_no_promotion(self):
        self.change("stage-02/completed-dossiers",
                    lambda doc: doc["claims"][0].update({"source_ids": ["invalid"]}))
        research = mod.read(self.area / "stage-02/completed-dossiers" / self.name)
        self.change("stage-03/inbox",
                    lambda doc: doc.update({"desk_research_sha256": mod.digest(research)}))
        stage3_packet = mod.read(self.area / "stage-03/inbox" / self.name)
        self.change("stage-02/receipts",
                    lambda doc: doc.update({"research_sha256": mod.digest(research),
                    "stage_3_packet_sha256": mod.digest(stage3_packet)}))
        self.assertEqual(mod.execute(self.root)["stage3_blocked_this_tick"], 1)

if __name__ == "__main__":
    unittest.main()
