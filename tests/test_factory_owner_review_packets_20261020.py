"""Review packet intake is genuine, private and never grants publication."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/factory_owner_review_packets_20261020.py"
spec = importlib.util.spec_from_file_location("owner_review_packets",PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ReviewPacketTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.orders = self.root/"production-instructions"/"orders"
        self.orders.mkdir(parents=True)
        self.orders.joinpath("WO-00000001.json").write_text(json.dumps({
            "id":"WO-00000001","status":"issued","phase":"engineering_specification",
            "origin":"factory_invention","subject":"Original offline worksheet"
        }))
        self.orders.joinpath("WO-00000002.json").write_text(json.dumps({
            "id":"WO-00000002","status":"issued","phase":"research_rework",
            "origin":"local-factory-research","blocker":"real evidence needed"
        }))

    def test_generated_private_review_is_not_a_passport_or_an_approval(self):
        report = m.build(self.root)
        self.assertEqual(report["counts"]["manufacturing_orders"],1)
        self.assertEqual(report["counts"]["research_waiting_for_real_evidence"],1)
        self.assertEqual(report["counts"]["missing_passport"],1)
        self.assertEqual(report["counts"]["new_private_packets"],1)
        self.assertEqual(report["products_activated"],0)
        self.assertEqual(report["sites_contacted"],0)
        queue=self.root/"product-lifecycle"/"owner-review-queue"
        candidates=list(queue.rglob("WO-00000001/*.json"))
        self.assertEqual(len(candidates),1)
        packet=json.loads(candidates[0].read_text())
        self.assertEqual(packet["schema"],m.SCHEMA)
        self.assertIn("independent_reviewer_id",packet["passport_fields_missing"])
        self.assertFalse(packet["commercial_release"])
        self.assertFalse(packet["manufacturing_approval"])
        self.assertFalse(packet["store_publication"])
        self.assertFalse((self.root/"product-lifecycle"/"passports").exists())
        self.assertEqual(candidates[0].stat().st_mode & 0o777,0o600)
        self.assertEqual(m.build(self.root)["counts"].get("new_private_packets",0),0)

    def test_invalid_order_and_symlink_are_refused(self):
        (self.orders/"WO-00000003.json").write_text(json.dumps({
            "id":"WO-00000004","status":"issued"
        }))
        with self.assertRaisesRegex(RuntimeError,"REVIEW_BAD_ORDER_PROVENANCE"):
            m.build(self.root)
        (self.orders/"WO-00000003.json").unlink()
        (self.orders/"extra.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError,"REVIEW_UNEXPECTED_ORDER_SOURCE"):
            m.build(self.root)

    def test_empty_existing_passport_never_grants_approval(self):
        path=self.root/"product-lifecycle"/"passports"
        path.mkdir(parents=True)
        (path/"WO-00000001.json").write_text(json.dumps({"work_order":"WO-00000001"}))
        result=m.build(self.root)
        self.assertEqual(result["counts"]["incomplete_passport"],1)
        self.assertEqual(result["approval_records_written"],0)
        self.assertEqual(result["products_activated"],0)

if __name__=="__main__":
    unittest.main()
