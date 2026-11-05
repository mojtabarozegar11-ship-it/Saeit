"""No cross-project evidence, invented score, or writable completion marker."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


RECIPE = Path(__file__).resolve().parents[1] / "product_recipes" / "farm_enterprise_economics"
SPEC = importlib.util.spec_from_file_location("evidence", RECIPE / "build_technical_evidence.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class FarmEvidenceCaptureTests(unittest.TestCase):
    def test_six_proofs_are_bound_to_real_source_and_never_autocertify(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "new-proof"
            result = MOD.build(RECIPE, folder)
            self.assertEqual(result["test_count"], 33)
            self.assertEqual(set(result["candidate_criteria"]), set(MOD.CRITERION_TESTS))
            self.assertIsNone(result["verified_quality_score"])
            self.assertFalse(result["independent_reviewer_approval"])
            self.assertFalse(result["commercial_release_allowed"])
            self.assertFalse(result["receiver_acceptance"])
            self.assertEqual(result["source_sha256"]["calculator.py"], MOD.sha256(RECIPE / "calculator.py"))
            self.assertEqual(result["source_sha256"]["build_technical_evidence.py"],
                             MOD.sha256(RECIPE / "build_technical_evidence.py"))
            self.assertEqual(result, json.loads((folder / "manifest.json").read_text()))
            for id, receipt in result["candidate_criteria"].items():
                proof = folder / receipt["path"]
                self.assertEqual(MOD.sha256(proof), receipt["sha256"])
                record = json.loads(proof.read_text())
                self.assertEqual(record["product_id"], MOD.PRODUCT)
                self.assertEqual(record["criterion_id"], id)
                self.assertFalse(record["independent_specialist_verified"])

    def test_existing_evidence_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "manifest.json").write_text("preserve me")
            with self.assertRaisesRegex(ValueError, "DESTINATION_NOT_EMPTY"):
                MOD.build(RECIPE, folder)
            self.assertEqual((folder / "manifest.json").read_text(), "preserve me")

    def test_failed_suite_does_not_create_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "failing-evidence"
            with patch.object(MOD, "execute", return_value="Ran 33 tests in 0.1s\nFAILED (failures=1)\n"):
                with self.assertRaisesRegex(ValueError, "TEST_SUITE_NOT_FULLY_PASSED"):
                    MOD.build(RECIPE, folder)
            self.assertFalse((folder / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
