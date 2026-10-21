import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "factory_family_evidence_suppliers_v1.py"
spec = importlib.util.spec_from_file_location("family_evidence_suppliers", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample_catalog():
    return {
        "schema": module.FAMILY_SCHEMA,
        "profiles": [
            {"id": "F%02d" % n, "slug": "family_%02d" % n,
             "producer_adapter": "adapter_%02d" % n,
             "specialist_tests": ["domain_check_%02d" % n]}
            for n in range(1, 41)
        ],
    }


class FamilyEvidenceSupplierTests(unittest.TestCase):
    def test_builds_one_distinct_supplier_per_registered_family(self):
        registry = module.build_supplier_registry(sample_catalog())
        self.assertEqual(registry["supplier_count"], 40)
        self.assertEqual(registry["connected_supplier_count"], 0)
        self.assertEqual(len({s["supplier_id"] for s in registry["suppliers"]}), 40)
        self.assertEqual(registry["evidence_fabricated"], False)
        self.assertTrue(all(s["evidence_request_capacity"] == "UNBOUNDED_APPEND_ONLY"
                            for s in registry["suppliers"]))

    def test_version_intake_is_bound_to_exact_family_build(self):
        registry = module.build_supplier_registry(sample_catalog())
        intake = module.build_version_intake(registry, "F28", "a" * 64, "b" * 64)
        self.assertEqual(intake["supplier_id"], "evidence_supplier_f28")
        self.assertEqual(intake["source_sha256"], "a" * 64)
        self.assertEqual(intake["artifact_sha256"], "b" * 64)
        self.assertGreater(len(intake["required_evidence"]), 0)
        self.assertFalse(intake["release_authorized"])

    def test_rejects_missing_or_reordered_family_catalog(self):
        catalog = sample_catalog()
        catalog["profiles"].pop()
        with self.assertRaisesRegex(ValueError, "FAMILY_CATALOG_CONTRACT_INVALID"):
            module.build_supplier_registry(catalog)
        catalog = sample_catalog()
        catalog["profiles"][0], catalog["profiles"][1] = catalog["profiles"][1], catalog["profiles"][0]
        with self.assertRaisesRegex(ValueError, "FAMILY_CATALOG_IDS_INVALID"):
            module.build_supplier_registry(catalog)

    def test_rejects_duplicate_family_slugs(self):
        catalog = sample_catalog()
        catalog["profiles"][1]["slug"] = catalog["profiles"][0]["slug"]
        with self.assertRaisesRegex(ValueError, "FAMILY_PROFILE_INVALID"):
            module.build_supplier_registry(catalog)


if __name__ == "__main__":
    unittest.main()
