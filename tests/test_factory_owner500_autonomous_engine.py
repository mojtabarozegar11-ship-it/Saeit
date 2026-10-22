"""Real unattended 500-backlog selection, native product making and failure recovery."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/"scripts"))
import factory_owner500_autonomous_engine as engine

CATALOG=BASE/"factory_config"/"owner_demand_500_20261022.json"
FORMULAS=BASE/"factory_config"/"owner500_autonomous_f28_formulas.json"
SNAPSHOT=BASE/"factory_config"/"owner_demand_500_factory_snapshot_20261022.json"

class AutonomousRealFactoryTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root=Path(td.name)
        (self.root/"production-order-inputs").mkdir()
        (self.root/"production-order-inputs"/"factory-invention-snapshot.json").write_bytes(SNAPSHOT.read_bytes())
        (self.root/"generated-product-recipes").mkdir()
        self.queue=json.loads(FORMULAS.read_text())
        self.queue["formulas"]=self.queue["formulas"][:2]
        self.queued=self.root/"queue.json"
        self.queued.write_text(json.dumps(self.queue))
    def tick(self):
        return engine.run(self.root,CATALOG,self.queued,BASE/"scripts",limit=1)

    def test_distinct_product_per_tick_then_explicit_idle(self):
        first=self.tick()
        self.assertEqual(first["supported_formula_briefs"],2)
        self.assertEqual(first["new_private_products_this_tick"],1)
        self.assertEqual(first["quality1000_certified"],0)
        self.assertEqual(first["website_deployments"],0)
        self.assertEqual(len(first["events"]),1)
        a=first["events"][0]
        self.assertEqual(a["owner_id"],"PD-0082")
        self.assertTrue(a["new_archive"])
        self.assertGreaterEqual(a["customer_tests"],5)
        second=self.tick()
        self.assertEqual(second["new_private_products_this_tick"],1)
        self.assertEqual(second["events"][0]["owner_id"],"PD-0083")
        self.assertNotEqual(a["artifact_sha256"],second["events"][0]["artifact_sha256"])
        third=self.tick()
        self.assertEqual(third["new_private_products_this_tick"],0)
        self.assertEqual(third["already_verified_skipped"],2)
        self.assertEqual(third["events"],[])
        self.assertEqual(third["verified_private_products"],2)
        self.assertEqual(len(list((self.root/"owner500-autonomous-production"/"receipts").glob("*.json"))),2)

    def test_fail_closed_after_owner_catalog_tamper(self):
        copied=json.loads(CATALOG.read_text())
        next(x for x in copied["products"] if x["id"]=="PD-0082")["quality1000_certified"]=True
        fake=self.root/"wrong-owner.json"
        fake.write_text(json.dumps(copied))
        with self.assertRaisesRegex(ValueError,"AUTONOMY_500_ITEM_NOT_VERIFIED"):
            engine.run(self.root,fake,self.queued,BASE/"scripts")
        self.assertFalse((self.root/"owner500-autonomous-production").exists())

    def test_cannot_infer_market_demand_or_release(self):
        result=self.tick()
        entry=result["items"]["PD-0082"]
        self.assertFalse(entry["quality1000_certified"])
        self.assertFalse(entry["publication_approved"])
        path=next((self.root/"owner500-autonomous-production"/"receipts").glob("*.json"))
        receipt=json.loads(path.read_text())
        self.assertFalse(receipt["independent_specialist_approval"])
        self.assertFalse(receipt["commercial_release"])
        self.assertEqual(receipt["site_changes"],0)

    def test_corrupted_archive_attempts_safe_repair(self):
        initial=self.tick()
        recipe=initial["events"][0]["recipe"]
        archive=self.root/"digital-products"/recipe/(recipe+"-internal-qa.zip")
        archive.write_bytes(b"corrupt")
        again=self.tick()
        self.assertEqual(again["events"][0]["owner_id"],"PD-0082")
        self.assertEqual(again["events"][0]["state"],"private_product_built")
        self.assertNotEqual(archive.read_bytes(),b"corrupt")
        self.assertFalse(again["items"]["PD-0082"]["quality1000_certified"])

    def test_symlink_input_is_rejected(self):
        link=self.root/"linked.json"
        link.symlink_to(FORMULAS)
        with self.assertRaisesRegex(ValueError,"UNSAFE_OR_MISSING"):
            engine.run(self.root,CATALOG,link,BASE/"scripts")

if __name__=="__main__":
    unittest.main()
