"""F01 evidence cannot cross product/ZIP boundaries or claim QC1000 release."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "product_recipes" / "farm_enterprise_economics"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load(RECIPE / "build_technical_evidence.py", "f01_capture")
bridge = load(ROOT / "scripts" / "f01_technical_evidence_bridge.py", "f01_bridge")


class F01TechnicalBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proofs = tempfile.TemporaryDirectory()
        cls.evidence = Path(cls.proofs.name) / "verified"
        builder.build(RECIPE, cls.evidence)

    @classmethod
    def tearDownClass(cls):
        cls.proofs.cleanup()

    def make_manufactured(self, base, *, stale=False):
        product = base / "farm_enterprise_economics"
        product.mkdir()
        archive = product / "farm_enterprise_economics-internal-qa.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for name in bridge.PACKAGE_SOURCES:
                data = (RECIPE / name).read_bytes()
                if stale and name == "calculator.py":
                    data += b"\n# Changed source version\n"
                package.writestr("farm_enterprise_economics/" + name, data)
        manifest = {"recipe": "farm_enterprise_economics", "qa_status": "passed",
                    "commercial_status": "private_internal_qa_pass_not_published",
                    "public_listing_enabled": False,
                    "owner_publication_approval": False,
                    "artifact_sha256": bridge.digest(archive)}
        (product / "manufacturing_manifest.json").write_text(json.dumps(manifest))
        return product

    def test_bind_six_internal_receipts_to_exact_private_zip_only(self):
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name))
            validated = bridge.verify(RECIPE, self.evidence)
            bridge.verify_manufactured(product, validated)
            records = bridge.install(product, validated)
            self.assertEqual(set(records), set(bridge.CRITERIA))
            candidate = json.loads((product / "global_quality_candidate.json").read_text())
            self.assertIsNone(candidate["f01_technical_evidence_import"]["verified_quality_points"])
            self.assertFalse(candidate["f01_technical_evidence_import"]["commercial_release_allowed"])
            self.assertFalse(candidate["f01_technical_evidence_import"]["receiver_acceptance"])
            self.assertEqual(records, bridge.install(product, validated))
            self.assertEqual(len(list((product / "evidence-f01").iterdir())), 1)

    def test_stale_manufactured_source_does_not_get_receipts(self):
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name), stale=True)
            with self.assertRaisesRegex(ValueError, "SOURCE_NOT_IN_EXACT_MANUFACTURED_ZIP"):
                bridge.install(product, bridge.verify(RECIPE, self.evidence))
            self.assertFalse((product / "global_quality_candidate.json").exists())
            self.assertFalse((product / "evidence-f01").exists())

    def test_modified_receipt_and_release_claim_are_rejected_read_only(self):
        with tempfile.TemporaryDirectory() as name:
            copied = Path(name) / "proof"
            shutil.copytree(self.evidence, copied)
            path = copied / "evidence-Q035.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "RECEIPT_HASH_MISMATCH"):
                bridge.verify(RECIPE, copied)
        with tempfile.TemporaryDirectory() as name:
            copied = Path(name) / "proof"
            shutil.copytree(self.evidence, copied)
            path = copied / "manifest.json"
            data = json.loads(path.read_text())
            data["commercial_release_allowed"] = True
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "MANIFEST_IDENTITY_OR_RELEASE_CLAIM"):
                bridge.verify(RECIPE, copied)

    def test_existing_conflicting_evidence_not_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name))
            prior = {"schema": "saeit.factory.global-quality-candidate.v1",
                     "recipe": "farm_enterprise_economics",
                     "criteria_evidence": {"Q035": {"path": "old.json", "sha256": "0" * 64}}}
            original = json.dumps(prior)
            (product / "global_quality_candidate.json").write_text(original)
            with self.assertRaisesRegex(ValueError, "EXISTING_EVIDENCE_CONFLICT"):
                bridge.install(product, bridge.verify(RECIPE, self.evidence))
            self.assertEqual((product / "global_quality_candidate.json").read_text(), original)
            self.assertFalse((product / "evidence-f01").exists())


if __name__ == "__main__":
    unittest.main()
