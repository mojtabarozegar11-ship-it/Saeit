"""Tests for 200-to-200 SKU/order identity and fail-closed readiness."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "scripts" / filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


G = load("agri200_exact_private_readiness_20261024.py", "agri200_exact_gate")
I = load("factory_agri200_p0_intake.py", "agri200_order_intake")
CATALOG = ROOT / "docs/agri200_p0_catalog.tsv"


class ExactLineageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.area = self.root / "production-instructions"
        queue = self.area / "orders"
        queue.mkdir(parents=True)
        self.rows = I.catalog(CATALOG)
        self.ids = []
        for n, (product_id, fa, en) in enumerate(self.rows, 1):
            order_id = f"WO-{n:08d}"
            item = dict(I.make_order(product_id, fa, en, n), id=order_id)
            (queue / (order_id + ".json")).write_text(
                json.dumps(item, ensure_ascii=False), encoding="utf-8")
            self.ids.append(order_id)
        self.index = {
            "schema": G.INDEX_SCHEMA,
            "topic_count": 200, "edition_goal_count": 400,
            "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
            "order_ids_ranked": self.ids,
        }
        self.write_index()

    def write_index(self):
        (self.area / "owner-agri200-p0-index.json").write_text(
            json.dumps(self.index), encoding="utf-8")

    def test_all_200_are_identity_bound_private_and_owner_discounts_zero(self):
        result = G.evaluate(CATALOG, self.root)
        self.assertEqual(result["factory_work_orders_mapped"], 200)
        self.assertEqual((result["mojplaywin_usd"], result["zomorod_irr"]), (100, 100))
        self.assertEqual(result["commercially_releasable"], 0)
        self.assertEqual(result["payments_initiated"], 0)
        self.assertIs(result["sites_changed"], False)
        self.assertEqual(len({row["source_order_id"] for row in result["products"]}), 200)
        for n, row in enumerate(result["products"], 1):
            self.assertEqual(row["product_id"], f"AGRI-{n:03d}")
            self.assertEqual(row["source_order_id"], self.ids[n-1])
            self.assertEqual(row["currency"], "USD" if n <= 100 else "IRR")
            self.assertEqual(row["discount_percent"], 0)
            self.assertFalse(row["sales_enabled"])
            self.assertFalse(row["public_listing_enabled"])
            self.assertFalse(row["qc1000_approved"])
            self.assertIn("TRUSTED_INDEPENDENT_QC1000_NOT_VERIFIED_HERE", row["blockers"])

    def test_reordered_work_order_cannot_be_sold_under_another_title(self):
        self.index["order_ids_ranked"][0], self.index["order_ids_ranked"][1] = (
            self.index["order_ids_ranked"][1], self.index["order_ids_ranked"][0])
        self.write_index()
        with self.assertRaisesRegex(ValueError, "ORDER_CATALOG_IDENTITY_MISMATCH"):
            G.evaluate(CATALOG, self.root)

    def test_modified_order_digest_is_rejected(self):
        path = self.area / "orders" / (self.ids[0] + ".json")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["source_sha256"] = "0" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ORDER_CATALOG_IDENTITY_MISMATCH"):
            G.evaluate(CATALOG, self.root)

    def test_wrong_catalog_hash_is_rejected(self):
        self.index["catalog_sha256"] = "0" * 64
        self.write_index()
        with self.assertRaisesRegex(ValueError, "P0_EXACT_CATALOG_LINEAGE_FAILED"):
            G.evaluate(CATALOG, self.root)

    def test_forged_internal_1000_status_never_becomes_commercial_clearance(self):
        folder = self.area / "stage-06/strict-qc1000"
        folder.mkdir(parents=True)
        (folder / (self.ids[0] + "--r001.json")).write_text(
            json.dumps({"quality1000_approved": True, "commercial_release": True}),
            encoding="utf-8")
        result = G.evaluate(CATALOG, self.root)
        first = result["products"][0]
        self.assertTrue(first["factory_signals"]["internal_qc_receipt_present"])
        self.assertFalse(first["qc1000_approved"])
        self.assertFalse(first["sales_enabled"])
        self.assertEqual(result["commercially_releasable"], 0)

    def test_rework_return_remains_blocked(self):
        folder = self.area / "stage-05/strict-qc-rework"
        folder.mkdir(parents=True)
        (folder / (self.ids[0] + "--r001.json")).write_text(
            json.dumps({"critical_findings": ["MISSING_FULLTEXT"]}), encoding="utf-8")
        row = G.evaluate(CATALOG, self.root)["products"][0]
        self.assertTrue(row["factory_signals"]["rework_receipt_present"])
        self.assertIn("REWORK_RETURNED_FOR_CORRECTION", row["blockers"])

    def test_unsafe_order_symlink_is_rejected(self):
        path = self.area / "orders" / (self.ids[0] + ".json")
        target = self.root / "other.json"
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "UNSAFE_EVIDENCE_FILE"):
            G.evaluate(CATALOG, self.root)


if __name__ == "__main__":
    unittest.main()
