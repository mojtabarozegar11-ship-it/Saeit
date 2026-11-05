"""No cross-project evidence, invented score, or writable completion marker."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


RECIPE = Path(__file__).resolve().parents[1] / "product_recipes" / "farm_enterprise_economics"
SPEC = importlib.util.spec_from_file_location("evidence", RECIPE / "build_technical_evidence.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class FarmEvidenceCaptureTests(unittest.TestCase):
    def test_eight_proofs_are_bound_to_real_source_and_never_autocertify(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "new-proof"
            result = MOD.build(RECIPE, folder)
            self.assertEqual(result["test_count"], 43)
            self.assertEqual(set(result["candidate_criteria"]), set(MOD.CRITERION_TESTS))
            self.assertEqual(len(result["candidate_criteria"]), 8)
            self.assertIn("Q057", result["candidate_criteria"])
            self.assertIn("Q065", result["candidate_criteria"])
            self.assertIsNone(result["verified_quality_score"])
            self.assertFalse(result["independent_reviewer_approval"])
            self.assertFalse(result["commercial_release_allowed"])
            self.assertFalse(result["receiver_acceptance"])
            self.assertEqual(result["source_sha256"]["calculator.py"], MOD.sha256(RECIPE / "calculator.py"))
            self.assertEqual(result["source_sha256"]["build_technical_evidence.py"],
                             MOD.sha256(RECIPE / "build_technical_evidence.py"))
            for required in ("guided_start.py", "test_guided_start.py", "CUSTOMER_GUIDE.md"):
                self.assertEqual(result["source_sha256"][required], MOD.sha256(RECIPE / required))
            covered_guided_tests = set().union(*(set(MOD.CRITERION_TESTS[key])
                                                for key in ("Q061", "Q063", "Q064")))
            expected_guided_tests = {
                "test_success_creates_four_consistent_reports_and_original_inputs",
                "test_invalid_numbers_and_duplicate_names_are_reprompted",
                "test_confirmation_is_fail_closed_and_creates_no_files",
                "test_each_export_goes_to_new_folder_without_overwrite",
                "test_output_parent_symlink_is_rejected_before_any_writes",
                "test_end_of_input_is_safe_cancellation",
                "test_verification_is_read_only_and_requires_no_interactive_answers",
                "test_modified_customer_report_is_detected_without_rewriting_it",
                "test_missing_manifest_or_symlink_report_is_not_accepted",
                "test_failed_export_has_no_completion_receipt",
            }
            self.assertTrue(expected_guided_tests.issubset(covered_guided_tests))
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
            with patch.object(MOD, "execute", return_value="Ran 43 tests in 0.1s\nFAILED (failures=1)\n"):
                with self.assertRaisesRegex(ValueError, "TEST_SUITE_NOT_FULLY_PASSED"):
                    MOD.build(RECIPE, folder)
            self.assertFalse((folder / "manifest.json").exists())

    def test_missing_customer_wizard_cannot_claim_complete_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            recipe = Path(directory) / "recipe"
            shutil.copytree(RECIPE, recipe)
            (recipe / "guided_start.py").unlink()
            target = Path(directory) / "evidence"
            with self.assertRaisesRegex(ValueError, "PRODUCT_RECIPE_FILES_MISSING"):
                MOD.build(recipe, target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
