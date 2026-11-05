"""No shared or symlinked file may inflate 100 independent documentary groups."""

import hashlib
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_quality_1000_v2.py"
SPEC = importlib.util.spec_from_file_location("quality_1000_documentary", SCRIPT)
QUALITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALITY)


def reference(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class DocumentaryProofUniquenessTests(unittest.TestCase):
    def test_one_proof_cannot_award_two_independent_criteria(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / "proof.txt"
            proof.write_text("Evidence record " * 5, encoding="utf-8")
            ref = reference(proof)
            graded = QUALITY.grade({"blockers": []}, criteria_evidence={
                "Q001": ref, "Q003": ref,
            }, evidence_root=root)
            self.assertEqual(graded["documentary_evidence_points"], 10)
            self.assertFalse(graded["release_allowed"])
            self.assertIsNone(graded["product_quality_points"])

    def test_duplicate_bytes_in_different_files_do_not_count_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one = root / "first.txt"
            two = root / "second.txt"
            one.write_text("Identical evidence " * 5, encoding="utf-8")
            two.write_bytes(one.read_bytes())
            graded = QUALITY.grade({"blockers": []}, criteria_evidence={
                "Q001": reference(one), "Q003": reference(two),
            }, evidence_root=root)
            self.assertEqual(graded["documentary_evidence_points"], 10)

    def test_distinct_proof_files_retain_distinct_documentary_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one = root / "first.txt"
            two = root / "second.txt"
            one.write_text("First criterion evidence " * 5, encoding="utf-8")
            two.write_text("Second criterion evidence " * 5, encoding="utf-8")
            graded = QUALITY.grade({"blockers": []}, criteria_evidence={
                "Q001": reference(one), "Q003": reference(two),
            }, evidence_root=root)
            self.assertEqual(graded["documentary_evidence_points"], 20)
            self.assertFalse(graded["professional_quality_1000_passed"])

    def test_symlink_inside_evidence_root_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "actual.txt"
            original.write_text("Protected criterion evidence " * 5, encoding="utf-8")
            alias = root / "alias.txt"
            alias.symlink_to(original)
            self.assertFalse(QUALITY.file_matches(root, reference(alias)))

    def test_one_proof_mapped_to_all_hundred_groups_earns_only_ten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / "same-proof.txt"
            proof.write_text("One technical document cannot attest every quality criterion. " * 3,
                             encoding="utf-8")
            graded = QUALITY.grade({"blockers": []}, criteria_evidence={
                key: reference(proof) for key in QUALITY.CRITERIA
            }, evidence_root=root)
            self.assertEqual(graded["documentary_evidence_points"], 10)
            self.assertEqual(graded["documentary_evidence_gap"], 990)
            self.assertEqual(sum(
                value["evidence_status"] == "DUPLICATE_EVIDENCE_REUSED"
                for value in graded["criteria"].values()), 99)
            self.assertIsNone(graded["product_quality_points"])
            self.assertFalse(graded["release_allowed"])

    def test_forged_scorecard_with_duplicate_credited_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / "proof.txt"
            proof.write_text("Hash-backed independent criterion evidence " * 3,
                             encoding="utf-8")
            graded = QUALITY.grade({"blockers": []}, criteria_evidence={
                "Q001": reference(proof), "Q003": reference(proof),
            }, evidence_root=root)
            tampered = copy.deepcopy(graded)
            tampered["criteria"]["Q003"]["documentary_points"] = 10
            tampered["documentary_evidence_points"] = 20
            tampered["documentary_evidence_gap"] = 980
            with self.assertRaisesRegex(RuntimeError,
                                        "DUPLICATE_OR_UNBOUND_QUALITY_EVIDENCE"):
                QUALITY.require_no_false_certification(tampered)

    def test_symlinked_parent_directory_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual_dir = root / "actual"
            actual_dir.mkdir()
            proof = actual_dir / "proof.txt"
            proof.write_text("Criterion source " * 8, encoding="utf-8")
            (root / "alias").symlink_to(actual_dir, target_is_directory=True)
            self.assertFalse(QUALITY.file_matches(root, {
                "path": "alias/proof.txt", "sha256": reference(proof)["sha256"],
            }))


if __name__ == "__main__":
    unittest.main()
