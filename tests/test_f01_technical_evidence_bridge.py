"""F01 evidence cannot cross product/ZIP boundaries or claim QC1000 release."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
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

    def test_failed_evidence_capture_can_retry_without_manual_cleanup(self):
        with tempfile.TemporaryDirectory() as name:
            destination = Path(name) / "evidence"
            with patch.object(builder, "execute", side_effect=ValueError("CAPTURE_FAILED")):
                with self.assertRaisesRegex(ValueError, "CAPTURE_FAILED"):
                    builder.build(RECIPE, destination)
            self.assertFalse(destination.exists(), "empty failed target must not block a retry")
            success = builder.build(RECIPE, destination)
            self.assertTrue((destination / "manifest.json").is_file())
            self.assertEqual(success["test_count"], 47)
            self.assertFalse(success["commercial_release_allowed"])

    def test_failed_capture_never_erases_partially_published_artifact(self):
        with tempfile.TemporaryDirectory() as name:
            destination = Path(name) / "evidence"

            def partial_capture(argv, cwd):
                (destination / "partial-preserve.txt").write_text("recoverable-evidence")
                raise ValueError("CAPTURE_FAILED")

            with patch.object(builder, "execute", side_effect=partial_capture):
                with self.assertRaisesRegex(ValueError, "CAPTURE_FAILED"):
                    builder.build(RECIPE, destination)
            self.assertEqual((destination / "partial-preserve.txt").read_text(),
                             "recoverable-evidence")
            self.assertFalse((destination / "manifest.json").exists())

    def make_manufactured(self, base, *, stale=False, omitted=None, stale_builder=False,
                          extra_zip_member=None, extra_declared_file=None):
        product = base / "farm_enterprise_economics"
        product.mkdir()
        archive = product / "farm_enterprise_economics-internal-qa.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for name in bridge.PACKAGE_SOURCES:
                if name == omitted:
                    continue
                data = (RECIPE / name).read_bytes()
                if stale and name == "calculator.py":
                    data += b"\n# Changed source version\n"
                if stale_builder and name == "build_technical_evidence.py":
                    data += b"\n# Obsolete criterion binding\n"
                package.writestr("farm_enterprise_economics/" + name, data)
            if extra_zip_member:
                package.writestr("farm_enterprise_economics/" + extra_zip_member, b"unreviewed")
        manifest = {"recipe": "farm_enterprise_economics", "qa_status": "passed",
                    "commercial_status": "private_internal_qa_pass_not_published",
                    "public_listing_enabled": False,
                    "owner_publication_approval": False,
                    "artifact_sha256": bridge.digest(archive),
                    "files": list(bridge.PACKAGE_SOURCES)
                    + ([extra_declared_file] if extra_declared_file else [])}
        (product / "manufacturing_manifest.json").write_text(json.dumps(manifest))
        return product

    def test_bind_eight_internal_receipts_to_exact_private_zip_only(self):
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name))
            validated = bridge.verify(RECIPE, self.evidence)
            bridge.verify_manufactured(product, validated)
            records = bridge.install(product, validated)
            self.assertEqual(set(records), set(bridge.CRITERIA))
            self.assertEqual(len(records), 8)
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

    def test_legacy_bundle_missing_wizard_cannot_get_new_receipts(self):
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name), omitted="guided_start.py")
            with self.assertRaisesRegex(ValueError, "SOURCE_NOT_IN_EXACT_MANUFACTURED_ZIP:guided_start.py"):
                bridge.install(product, bridge.verify(RECIPE, self.evidence))
            self.assertFalse((product / "global_quality_candidate.json").exists())
            self.assertFalse((product / "evidence-f01").exists())

    def test_stale_evidence_builder_in_zip_cannot_get_new_receipts(self):
        """Criterion bindings are only credible for the exact packaged builder."""
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name), stale_builder=True)
            with self.assertRaisesRegex(
                ValueError, "SOURCE_NOT_IN_EXACT_MANUFACTURED_ZIP:build_technical_evidence.py"
            ):
                bridge.install(product, bridge.verify(RECIPE, self.evidence))
            self.assertFalse((product / "global_quality_candidate.json").exists())
            self.assertFalse((product / "evidence-f01").exists())

    def test_unlisted_zip_member_cannot_hide_in_valid_product(self):
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name), extra_zip_member="unexpected.py")
            with self.assertRaisesRegex(ValueError, "MANUFACTURED_ZIP_INVENTORY_MISMATCH"):
                bridge.install(product, bridge.verify(RECIPE, self.evidence))
            self.assertFalse((product / "global_quality_candidate.json").exists())

    def test_declared_but_missing_zip_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            product = self.make_manufactured(Path(name), extra_declared_file="BENCHMARKS_2026-11-03.md")
            with self.assertRaisesRegex(ValueError, "MANUFACTURED_ZIP_INVENTORY_MISMATCH"):
                bridge.install(product, bridge.verify(RECIPE, self.evidence))
            self.assertFalse((product / "global_quality_candidate.json").exists())

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

    def test_rehashed_receipt_cannot_borrow_unrelated_valid_test_names(self):
        with tempfile.TemporaryDirectory() as name:
            copied = Path(name) / "proof"
            shutil.copytree(self.evidence, copied)
            path = copied / "evidence-Q035.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            # This test exists and passes, but verifies user input validation,
            # not the farm economics reproducibility claimed by Q035.
            record["selected_passing_tests"] = [
                "test_invalid_numbers_and_duplicate_names_are_reprompted"
            ]
            path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["candidate_criteria"]["Q035"]["sha256"] = bridge.digest(path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RECEIPT_WRONG_TEST_BINDING"):
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
