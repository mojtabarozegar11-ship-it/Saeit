"""Prove 500 owner needs now yield three genuinely-built, separately QA-tested F28 artifacts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import factory_owner500_f28_real_builder as pilot

CATALOG = BASE / "factory_config" / "owner_demand_500_20261022.json"
SNAP = BASE / "factory_config" / "owner_demand_500_factory_snapshot_20261022.json"

class OwnerF28Handoff(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        intake = self.root / "production-order-inputs"
        intake.mkdir()
        (intake / "factory-invention-snapshot.json").write_bytes(SNAP.read_bytes())
        (self.root / "generated-product-recipes").mkdir()

    def run_pilot(self, limit=3):
        return pilot.produce(self.root, CATALOG, BASE / "scripts", limit)

    def test_three_real_products_built_and_independently_extracted(self):
        state = self.run_pilot()
        self.assertEqual(state["selected_owner_items"], 3)
        self.assertEqual(state["new_source_recipes"], 3)
        self.assertEqual(state["newly_built_or_updated_packages"], 3)
        self.assertEqual(state["independent_customer_qa_passed"], 3)
        self.assertEqual(state["website_deployments"], 0)
        self.assertEqual(state["professional_quality_1000_certified"], 0)
        self.assertEqual(state["remaining_unproven_or_unbuilt_needs"], 497)
        self.assertEqual({r["owner_item_id"] for r in state["product_receipts"]},
                         set(pilot.TARGETS))
        self.assertEqual(len({r["artifact_sha256"] for r in state["product_receipts"]}), 3)
        for rec in state["product_receipts"]:
            path = self.root / "digital-products" / rec["recipe"]
            self.assertTrue((path / (rec["recipe"] + "-internal-qa.zip")).is_file())
            self.assertFalse(rec["publication_approved"])
            self.assertFalse(rec["professional_quality_1000_certified"])
            self.assertGreaterEqual(rec["customer_zip_tests"], 5)
        self.assertEqual(len(list((self.root / "owner-demand-pilot").glob("PD-*.json"))), 3)

    def test_rerun_same_owner_requests_does_not_fabricate_new_products(self):
        one = self.run_pilot()
        two = self.run_pilot()
        self.assertEqual(two["new_source_recipes"], 0)
        self.assertEqual(two["newly_built_or_updated_packages"], 0)
        self.assertEqual(len(list((self.root / "owner-demand-pilot").glob("PD-*.json"))), 3)
        self.assertEqual({r["artifact_sha256"] for r in one["product_receipts"]},
                         {r["artifact_sha256"] for r in two["product_receipts"]})

    def test_false_owner_snapshot_product_or_title_is_rejected(self):
        source = self.root / "production-order-inputs" / "factory-invention-snapshot.json"
        doc = json.loads(source.read_text())
        item = next(x for x in doc["items"] if x["id"] == "factory_500_0196")
        item["title"] = "Wrong demo title"
        source.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "LIVE_VPS_SOURCE_MISMATCH"):
            self.run_pilot()
        self.assertFalse((self.root / "digital-products").exists())

    def test_owner_catalog_fake_qa_is_rejected(self):
        doc = json.loads(CATALOG.read_text())
        next(x for x in doc["products"] if x["id"] == "PD-0197")["quality1000_certified"] = True
        fake = self.root / "catalog.json"
        fake.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "OWNER_ITEM_NOT_ELIGIBLE"):
            pilot.produce(self.root, fake, BASE / "scripts")
        self.assertFalse((self.root / "digital-products").exists())

    def test_unsupported_target_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNSAFE_ROOT_OR_LIMIT"):
            self.run_pilot(4)

if __name__ == "__main__":
    unittest.main()
