"""Stage 2 acceptance tests: real source-to-claim handoff; missing evidence never passes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, BASE / rel)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

STAGE1 = load("stage1_research_support", "scripts/factory_stage1_handoff.py")
STAGE2 = load("stage2_research_worker", "scripts/factory_stage2_research.py")
AGRI = load("agri_research_factory", "scripts/factory_agri200_p0_intake.py")
SEED = json.loads((BASE / "docs/agri_p0_stage2_curated_research_sources_20261022.json").read_text())
CATALOG = BASE / "docs/agri200_p0_catalog.tsv"


class StageTwoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.area = self.root / "production-instructions"
        self.root.mkdir(exist_ok=True)
        self.rows = AGRI.catalog(CATALOG)

    def stage1(self, topic=1, serial=1):
        key, fa, en = self.rows[topic-1]
        doc = dict(AGRI.make_order(key, fa, en, topic),
                   id="WO-%08d" % serial)
        STAGE1.forward(self.root, doc)
        return doc

    def research_source(self, order, topic):
        original = copy.deepcopy(SEED["bundles"][topic-1])
        original["work_order_sha256"] = STAGE2.sha(order)
        path = self.area / "stage-02/source-evidence" / (
            order["source_product_id"] + "--r001.json")
        STAGE2.atomic(path, original)
        return original

    def test_order_and_revision_ids_expand(self):
        self.assertIsNotNone(STAGE2.ORDER_ID.fullmatch("WO-100000000"))
        match = STAGE2.INBOX_FILE.fullmatch("WO-100000000--r1000.json")
        self.assertIsNotNone(match)
        self.assertEqual((match.group(1), int(match.group(2))), ("WO-100000000", 1000))

    def test_missing_sources_stay_in_stage2_and_cannot_fake_completion(self):
        self.stage1()
        report = STAGE2.stage2_loop(self.root)
        self.assertEqual(report["newly_completed_research_dossiers"], 0)
        self.assertEqual(report["newly_documented_missing_sources"], 1)
        self.assertEqual(report["stage_2_research_briefs_total"], 1)
        self.assertFalse((self.area / "stage-03").exists())
        self.assertEqual(STAGE2.stage2_loop(self.root)["newly_documented_missing_sources"], 0)

    def test_curated_research_reaches_stage3_only_with_traceable_sources(self):
        order = self.stage1()
        evidence = self.research_source(order, 1)
        metrics = STAGE2.validate_evidence(evidence, order, 1)
        self.assertEqual(metrics["claim_count"], 5)
        self.assertEqual(metrics["publisher_count"], 4)
        report = STAGE2.stage2_loop(self.root)
        self.assertEqual(report["newly_completed_research_dossiers"], 1)
        out = self.area / "stage-03/inbox/WO-00000001--r001.json"
        doc = STAGE2.read(out)
        self.assertFalse(doc["independent_expert_review"])
        self.assertFalse(doc["quality1000_approved"])
        self.assertFalse(doc["public_distribution_allowed"])
        self.assertEqual(doc["stage_3_status"], "received_pending_design")
        self.assertEqual(STAGE2.stage2_loop(self.root)["newly_completed_research_dossiers"], 0)
        self.assertEqual(len(list((self.area / "stage-03/inbox").glob("*.json"))), 1)

    def test_invalid_unsupported_claim_blocks_stage3(self):
        order = self.stage1()
        content = self.research_source(order, 1)
        content["claims"][1]["source_ids"] = ["unknown"]
        STAGE2.atomic(self.area / "stage-02/source-evidence/AGRI-001--r001.json", content)
        report = STAGE2.stage2_loop(self.root)
        self.assertEqual(report["blocked_invalid_inputs"], 1)
        self.assertEqual(report["stage_3_handoffs_total"], 0)

    def test_tampered_stage1_packet_does_not_advance(self):
        self.stage1()
        pkt = self.area / "stage-02/inbox/WO-00000001--r001.json"
        obj = STAGE2.read(pkt)
        obj["source_order_sha256"] = "0"*64
        STAGE2.atomic(pkt, obj)
        self.research_source(obj["work_order"], 1)
        report = STAGE2.stage2_loop(self.root)
        self.assertEqual(report["blocked_invalid_inputs"], 1)
        self.assertFalse((self.area / "stage-03").exists())

    def test_p0_always_precedes_standard_order(self):
        self.stage1(4, 1)
        self.stage1(1, 2)
        a = STAGE2.stage2_loop(self.root, batch=1)
        self.assertEqual(a["newly_documented_missing_sources"], 1)
        self.assertTrue((self.area / "stage-02/research-needed/WO-00000002--r001.json").exists())
        self.assertFalse((self.area / "stage-02/research-needed/WO-00000001--r001.json").exists())

    def test_all_three_researched_topics_complete_without_independent_expert_claim(self):
        for topic in range(1, 4):
            order = self.stage1(topic, topic)
            self.research_source(order, topic)
        report = STAGE2.stage2_loop(self.root)
        self.assertEqual(report["newly_completed_research_dossiers"], 3)
        self.assertEqual(report["stage_3_handoffs_total"], 3)
        self.assertFalse(report["scientific_review_independently_verified"])
        self.assertFalse((self.root / "production-warehouse").exists())

    def test_source_domain_independence_is_required(self):
        order = self.stage1()
        content = self.research_source(order, 1)
        for entry in content["sources"]:
            entry["publisher"] = "One Publisher"
            entry["url"] = "https://same.example.org/" + entry["id"]
        with self.assertRaisesRegex(ValueError, "STAGE2_SOURCES_NOT_INDEPENDENT"):
            STAGE2.validate_evidence(content, order, 1)

    def test_genuine_return_from_stage3_is_researched_and_reissued_at_revision2(self):
        order = self.stage1()
        evidence = self.research_source(order, 1)
        self.assertEqual(STAGE2.stage2_loop(self.root)["newly_completed_research_dossiers"], 1)
        original = STAGE2.read(self.area /
            "stage-02/completed-dossiers/WO-00000001--r001.json")
        returned = {
            "schema": STAGE2.RETURN_SCHEMA, "order_id": order["id"],
            "revision": 2, "target_stage": 2, "source_stage": 3,
            "reason": "Design needs independently linked diagnostic distinctions",
            "previous_research_sha256": STAGE2.sha(original)
        }
        STAGE2.atomic(self.area / "stage-02/return-inbox/WO-00000001--r002.json", returned)
        self.assertEqual(STAGE2.stage2_loop(self.root)["newly_documented_missing_sources"], 1)
        revised = dict(evidence, revision=2)
        revised["claims"] = copy.deepcopy(evidence["claims"])
        revised["claims"][0]["statement"] += " Keep the underlying observations explicit."
        STAGE2.atomic(self.area / "stage-02/source-evidence/AGRI-001--r002.json", revised)
        result = STAGE2.stage2_loop(self.root)
        self.assertEqual(result["newly_completed_research_dossiers"], 1)
        self.assertTrue((self.area / "stage-03/inbox/WO-00000001--r002.json").exists())
        self.assertEqual(STAGE2.stage2_loop(self.root)["newly_completed_research_dossiers"], 0)

    def test_fake_stage3_return_is_rejected(self):
        order = self.stage1()
        self.research_source(order, 1)
        STAGE2.stage2_loop(self.root)
        invalid = {
            "schema": STAGE2.RETURN_SCHEMA, "order_id": order["id"],
            "revision": 2, "target_stage": 2, "source_stage": 3,
            "reason": "Material requires more research evidence",
            "previous_research_sha256": "0"*64
        }
        STAGE2.atomic(self.area / "stage-02/return-inbox/WO-00000001--r002.json", invalid)
        with self.assertRaisesRegex(RuntimeError, "STAGE2_UNTRUSTED_RETURN"):
            STAGE2.stage2_loop(self.root)

    def test_seeding_real_catalog_requires_index_and_all_200_stage1_receipts(self):
        AGRI.install(self.root, CATALOG)
        self.assertEqual(STAGE1.run(self.root, batch=250)["new_handoffs"], 200)
        amount = STAGE2.safe_catalog_seed(self.root,
            BASE / "docs/agri_p0_stage2_curated_research_sources_20261022.json")
        self.assertEqual(amount, 10)
        self.assertEqual(STAGE2.safe_catalog_seed(self.root,
            BASE / "docs/agri_p0_stage2_curated_research_sources_20261022.json"), 0)
        status = STAGE2.stage2_loop(self.root, batch=200)
        self.assertEqual(status["newly_completed_research_dossiers"], 10)
        self.assertEqual(status["newly_documented_missing_sources"], 190)
        self.assertEqual(status["stage_3_handoffs_total"], 10)
        self.assertEqual(status["stage_2_research_briefs_total"], 190)


if __name__ == "__main__":
    unittest.main()
