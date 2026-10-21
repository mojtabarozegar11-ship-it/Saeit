"""Actual evidence supplier: 100 obligations, exact stock and no fake approvals."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/factory_quality_evidence_supplier_v1.py"
spec = importlib.util.spec_from_file_location("supply_quality", SOURCE)
supplier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supplier)
CATALOG = ROOT / "factory_config/quality_100_criteria.json"


class EvidenceSupplierTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="evidence-supply-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipe = "greenhouse_crop_margin"
        self.source = "a" * 64
        self.version = (self.root / "production-warehouse" / "finished" /
                        self.recipe / self.source)
        self.version.mkdir(parents=True)
        self.product = self.version / "product.zip"
        with zipfile.ZipFile(str(self.product), "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(self.recipe + "/README.md", "sample only\n")
            z.writestr(self.recipe + "/calculator.py", "print('okay')\n")
        self.actual_sha = hashlib.sha256(self.product.read_bytes()).hexdigest()
        self.manifest = self.version / "warehouse_manifest.json"
        self.manifest.write_text(json.dumps({
            "schema": "saeit.factory.production-warehouse.v1",
            "product_id": self.recipe, "source_sha256": self.source,
            "artifact_sha256": self.actual_sha, "manufacturing_qc": "passed",
            "commercial_release": False, "site_transfer_state": "not_transferred",
            "bytes": self.product.stat().st_size,
        }), encoding="utf8")
        self.criteria = supplier.catalog(CATALOG)

    def dossier(self):
        return supplier.supplier_dossier(
            self.root, self.criteria, self.recipe, self.source, self.actual_sha)

    def test_all_100_have_real_supply_routes_with_explicit_unconnected_review(self):
        dossier = self.dossier()
        self.assertEqual(dossier["criteria_total"], 100)
        self.assertEqual(len(dossier["possible_supplier_roles"]), 10)
        self.assertEqual(len(dossier["supplier_assignments"]), 100)
        self.assertEqual(sum(1 for x in dossier["supplier_assignments"].values()
                             if x["automated_evidence_executable_now"]), 2)
        self.assertTrue(dossier["supplier_assignments"]["Q068"]["automated_evidence_executable_now"])
        self.assertFalse(dossier["supplier_assignments"]["Q033"]["automated_evidence_executable_now"])
        self.assertFalse(dossier["supplier_assignments"]["Q100"]["supplier_identity_authenticated"])
        self.assertEqual(dossier["q068_original_warehouse_zip_measurement"]["member_count"], 2)
        self.assertTrue(dossier["q068_original_warehouse_zip_measurement"]["zip_crc_verified"])
        binding = dossier["q092_exact_version_binding_measurement"]
        self.assertEqual(binding["artifact_sha256"], self.actual_sha)
        self.assertEqual(binding["warehouse_manifest_sha256"],
                         hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        self.assertFalse(binding["source_bytes_independently_verified"])
        self.assertEqual(dossier["unmet_criterion_count"], 98)
        self.assertIsNone(dossier["professional_quality_1000_points"])
        self.assertFalse(dossier["sale_or_publication_allowed"])

    def test_repeated_receipt_is_identical_and_original_warehouse_untouched(self):
        original = self.product.read_bytes()
        dossier = self.dossier()
        first = supplier.persist(self.root, dossier)
        second = supplier.persist(self.root, dossier)
        self.assertEqual(first, second)
        self.assertEqual(self.product.read_bytes(), original)
        self.assertTrue(Path(first["receipt"]).is_file())
        self.assertEqual(first["receipt_sha256"], hashlib.sha256(
            Path(first["receipt"]).read_bytes()).hexdigest())
        self.assertFalse(first["quality_1000_certified"])

    def test_wrong_artifact_hash_and_forged_sales_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "HASH_OR_POLICY_MISMATCH"):
            supplier.supplier_dossier(self.root, self.criteria, self.recipe,
                                      self.source, "b" * 64)
        m = json.loads(self.manifest.read_text())
        m["commercial_release"] = True
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(RuntimeError, "HASH_OR_POLICY_MISMATCH"):
            self.dossier()

    def test_tampered_zip_and_duplicate_paths_rejected(self):
        self.product.write_bytes(self.product.read_bytes() + b"tampered")
        with self.assertRaisesRegex(RuntimeError, "HASH_OR_POLICY_MISMATCH"):
            self.dossier()
        with zipfile.ZipFile(str(self.product), "w") as z:
            z.writestr(self.recipe + "/a.txt", "A")
            z.writestr(self.recipe + "/a.txt", "B")
        self.actual_sha = hashlib.sha256(self.product.read_bytes()).hexdigest()
        m = json.loads(self.manifest.read_text())
        m["artifact_sha256"] = self.actual_sha
        m["bytes"] = self.product.stat().st_size
        m["commercial_release"] = False
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(RuntimeError, "SUPPLIER_ZIP_UNSAFE_MEMBER"):
            self.dossier()

    def test_existing_receipt_cannot_be_silently_replaced(self):
        saved = supplier.persist(self.root, self.dossier())
        path = Path(saved["receipt"])
        path.write_bytes(b"malicious alteration")
        with self.assertRaisesRegex(RuntimeError, "SUPPLIER_IMMUTABLE_RECEIPT_CONFLICT"):
            supplier.persist(self.root, self.dossier())


    def test_real_f28_embedded_customer_runtime_supplies_seven_scoped_criteria(self):
        recipe_dir = ROOT / "product_recipes" / self.recipe
        with zipfile.ZipFile(str(self.product), "w", zipfile.ZIP_DEFLATED) as z:
            for name in supplier.F28_FILES:
                z.write(str(recipe_dir / name), self.recipe + "/" + name)
        self.actual_sha = hashlib.sha256(self.product.read_bytes()).hexdigest()
        manifest = json.loads(self.manifest.read_text())
        manifest["artifact_sha256"] = self.actual_sha
        manifest["bytes"] = self.product.stat().st_size
        self.manifest.write_text(json.dumps(manifest))
        with mock.patch.object(supplier, "PINNED_F28_SOURCE", self.source), \
             mock.patch.object(supplier, "PINNED_F28_ARTIFACT", self.actual_sha):
            record = self.dossier()
        self.assertEqual(record["automated_criteria_measured"],
                         ["Q036", "Q057", "Q061", "Q064", "Q068", "Q069", "Q092"])
        runtime = record["f28_runtime_technical_measurement"]
        self.assertGreaterEqual(runtime["actual_embedded_unittest_count"], 8)
        self.assertEqual(runtime["positive_baseline_cli_repeats"], 8)
        self.assertEqual(runtime["invalid_cli_inputs_rejected"], 8)
        self.assertEqual(record["unmet_criterion_count"], 93)
        self.assertEqual(record["independently_unapproved_criterion_count"], 100)
        self.assertEqual(record["independent_external_assessments_completed"], 0)
        self.assertFalse(record["sale_or_publication_allowed"])
        self.assertIsNone(record["professional_quality_1000_points"])

    def test_unpinned_f28_zip_cannot_execute_customer_code(self):
        with self.assertRaisesRegex(RuntimeError, "PINNED_PRODUCT_SHA"):
            supplier.f28_runtime_proof(self.product)


if __name__ == "__main__":
    unittest.main()
