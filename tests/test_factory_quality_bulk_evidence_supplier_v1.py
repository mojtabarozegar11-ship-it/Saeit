import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BulkEvidenceSupplierTests(unittest.TestCase):
    def test_all_valid_finished_versions_get_hash_bound_q068_receipts(self):
        bulk = load(ROOT / "scripts/factory_quality_bulk_evidence_supplier_v1.py", "bulk_supplier_test")
        supplier_path = ROOT / "scripts/factory_quality_evidence_supplier_v1.py"
        source_sha = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version = root / "production-warehouse/finished/sample_product" / source_sha
            version.mkdir(parents=True)
            archive = version / "product.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as out:
                out.writestr("sample_product/README.md", "real fixture bytes")
            artifact_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            manifest = {
                "schema": "saeit.factory.production-warehouse.v1",
                "product_id": "sample_product",
                "source_sha256": source_sha,
                "artifact_sha256": artifact_sha,
                "manufacturing_qc": "passed",
                "commercial_release": False,
                "site_transfer_state": "not_transferred",
                "bytes": archive.stat().st_size,
            }
            (version / "warehouse_manifest.json").write_text(json.dumps(manifest), encoding="utf8")
            policy_path = root / "catalog.json"
            groups = {"Q%03d" % i: {"name": "Criterion %03d" % i,
                                    "maximum_points": 10, "quality_dimensions": []}
                      for i in range(1, 101)}
            policy_path.write_text(json.dumps({
                "schema": "saeit.factory.quality-100-groups.v2", "group_count": 100,
                "points_per_group": 10, "total_points": 1000, "groups": groups,
            }), encoding="utf8")
            result = bulk.run(root, policy_path, supplier_path)
            self.assertEqual(result["versions_seen"], 1)
            self.assertEqual(result["versions_supplied"], 1)
            self.assertEqual(result["versions_rejected_or_unmeasurable"], 0)
            receipt = root / "quality-excellence/evidence-suppliers/sample_product" / source_sha
            docs = list(receipt.glob("supply-*.json"))
            self.assertEqual(len(docs), 1)
            dossier = json.loads(docs[0].read_text(encoding="utf8"))
            self.assertEqual(dossier["artifact_sha256"], artifact_sha)
            self.assertTrue(dossier["q068_original_warehouse_zip_measurement"]["zip_crc_verified"])
            self.assertFalse(dossier["professional_quality_1000_certified"])


if __name__ == "__main__":
    unittest.main()
