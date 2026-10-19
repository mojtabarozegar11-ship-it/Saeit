import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "factory_p0_improvement.py"
spec = importlib.util.spec_from_file_location("factory_p0_improvement", SOURCE)
p0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p0)


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


class P0MeasuredImprovementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "production-instructions" / "orders").mkdir(parents=True)
        (self.root / "product-lifecycle" / "approved-finished-goods").mkdir(parents=True)
        put(self.root / "product-lifecycle" / "dashboard.json", {
            "schema": p0.LIFECYCLE, "site_distribution_enabled": False,
            "final_commercially_verified_stock": 0, "open_defects": 0,
            "research_only_work_orders": 300,
            "workorder_status": {"awaiting_complete_passport": 1}})
        put(self.root / "production-family-management" / "family-dashboard.json", {
            "schema": p0.MASTER, "registered_families": 40,
            "distribution_enabled": False})
        put(self.root / "production-warehouse" / "stock-register.json", {
            "finished_goods_versions": 12, "sites_contacted": 0})
        put(self.root / "production-instructions" / "orders" / "WO-00000001.json", {
            "id": "WO-00000001", "phase": "engineering_specification",
            "fingerprint": "a" * 64})

    def approved_item(self):
        wid = "WO-00000001"
        base = self.root / "product-lifecycle"
        folder = base / "approved-finished-goods" / wid
        folder.mkdir(parents=True)
        zip_path = folder / "product.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("product/app.txt", "genuinely present, not final certified by P0")
        passport = base / "passports" / (wid + ".json")
        put(passport, {"work_order": wid, "title": "existing independently approved product"})
        put(base / "records" / (wid + ".json"), {
            "id": wid, "status": "in_finished_goods_warehouse_not_distributed",
            "final_warehouse_id": wid,
            "stage_status": {str(i): "passed" for i in range(1, 11)},
            "defects": []})
        put(folder / "receipt.json", {
            "schema": p0.LIFECYCLE, "order": wid,
            "stage_gates_passed": 10,
            "distributed": False, "sites_contacted": 0,
            "artifact_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
            "passport_sha256": hashlib.sha256(passport.read_bytes()).hexdigest()})
        doc = json.loads((base / "dashboard.json").read_text())
        doc["final_commercially_verified_stock"] = 1
        put(base / "dashboard.json", doc)

    def test_bootstrap_real_remediation_without_fake_finished_goods(self):
        first = p0.tick(self.root)
        self.assertEqual(first["verified_approved_stock"], 0)
        self.assertEqual(first["new_verified_products_since_last_tick"], 0)
        self.assertEqual(first["new_rework_tickets"], ["WO-00000001"])
        self.assertEqual(first["site_telemetry"]["mojplaywin"]["status"], "unobserved")
        second = p0.tick(self.root)
        self.assertEqual(second["new_rework_tickets"], [])
        self.assertFalse(second["measured_product_improvement"])

    def test_only_new_admitted_hash_consistent_good_counts(self):
        p0.tick(self.root)
        self.approved_item()
        later = p0.tick(self.root)
        self.assertEqual(later["new_verified_products_since_last_tick"], 1)
        self.assertTrue(later["measured_product_improvement"])
        self.assertFalse(later["auto_site_publish"])
        self.assertFalse(later["generation_auto_promotion"])

    def test_bad_dashboard_cannot_claim_fake_inventory(self):
        path = self.root / "product-lifecycle" / "dashboard.json"
        data = json.loads(path.read_text())
        data["final_commercially_verified_stock"] = 999
        put(path, data)
        with self.assertRaisesRegex(RuntimeError, "P0_DASHBOARD_GOODS_DISAGREE"):
            p0.tick(self.root)

    def test_regression_freezes_promotion(self):
        self.approved_item()
        p0.tick(self.root)
        doc = json.loads((self.root / "product-lifecycle" / "dashboard.json").read_text())
        doc["open_defects"] = 1
        put(self.root / "product-lifecycle" / "dashboard.json", doc)
        report = p0.tick(self.root)
        self.assertEqual(report["status"], "regression_freeze")
        self.assertTrue(report["rollback_or_human_review_required"])

    def test_private_telemetry_does_not_fake_site_products(self):
        put(self.root / "p0-improvement" / "site-telemetry" / "zomorodmelal.json", {
            "schema": p0.SCHEMA, "site": "zomorodmelal",
            "trusted_collection": True, "claimed_product_count": 5000})
        report = p0.tick(self.root)
        self.assertIsNone(report["site_telemetry"]["zomorodmelal"]["verified_new_products"])

    def test_symlinked_source_fails_closed(self):
        source = self.root / "product-lifecycle" / "dashboard.json"
        source.unlink()
        source.symlink_to(self.root / "production-family-management" / "family-dashboard.json")
        with self.assertRaisesRegex(RuntimeError, "P0_INVALID_EVIDENCE_FILE"):
            p0.tick(self.root)


if __name__ == "__main__":
    unittest.main()
