"""No-write rollback planning regression for self-generated AVA code edits."""

import unittest

from ava_core import CodeEdit, CodeEvolutionDirector, CodeProposal, CodeProposalError


class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.director = CodeEvolutionDirector(owner_id="owner")
        self.path = "ava_core/example.py"
        self.old = "value = 1\n"
        self.new = "value = 2\n"
        self.before = {self.path: self.old}
        self.current = {self.path: self.new}
        self.review = self.director.stage(
            CodeProposal("Fix code", "Improve internal logic", (
                CodeEdit(self.path, self.director.digest(self.old), self.new),
            )), trusted_files=self.before,
        )

    def plan(self, before=None, current=None):
        return self.director.prepare_rollback(
            self.review.review_id,
            trusted_before=self.before if before is None else before,
            trusted_current=self.current if current is None else current,
        )

    def test_existing_code_restore_plan_has_exact_old_source(self):
        plan = self.plan()
        self.assertEqual(plan.owner_id, "owner")
        self.assertEqual(plan.review_id, self.review.review_id)
        self.assertEqual(plan.files[0].action, "restore")
        self.assertEqual(plan.files[0].previous_source, self.old)
        self.assertEqual(plan.files[0].previous_sha256, self.director.digest(self.old))
        self.assertEqual(plan.files[0].expected_current_sha256, self.director.digest(self.new))

    def test_rollback_never_writes_trusted_tree(self):
        self.plan()
        self.assertEqual(self.before[self.path], self.old)
        self.assertEqual(self.current[self.path], self.new)

    def test_new_file_has_remove_intention_not_executed(self):
        path = "ava_core/new_module.py"
        source = "def feature():\n    return True\n"
        review = self.director.stage(
            CodeProposal("Add new internal code", "New behavior", (
                CodeEdit(path, None, source),
            )), trusted_files={},
        )
        current = {path: source}
        plan = self.director.prepare_rollback(
            review.review_id, trusted_before={}, trusted_current=current,
        )
        self.assertEqual(plan.files[0].action, "remove")
        self.assertIsNone(plan.files[0].previous_source)
        self.assertIn(path, current)

    def test_unknown_review_cannot_generate_rollback_plan(self):
        with self.assertRaises(CodeProposalError):
            self.director.prepare_rollback(
                "unknown", trusted_before=self.before, trusted_current=self.current,
            )

    def test_current_source_conflict_blocks_rollback(self):
        with self.assertRaises(CodeProposalError):
            self.plan(current={self.path: "value = 999\n"})

    def test_missing_current_source_blocks_rollback(self):
        with self.assertRaises(CodeProposalError):
            self.plan(current={})

    def test_wrong_original_source_blocks_rollback(self):
        with self.assertRaises(CodeProposalError):
            self.plan(before={self.path: "value = 999\n"})

    def test_missing_original_source_blocks_rollback(self):
        with self.assertRaises(CodeProposalError):
            self.plan(before={})

    def test_added_file_cannot_claim_an_existing_baseline(self):
        path = "ava_core/new_module.py"
        review = self.director.stage(
            CodeProposal("Add code", "New behavior", (CodeEdit(path, None, "answer=3\n"),)),
            trusted_files={},
        )
        with self.assertRaises(CodeProposalError):
            self.director.prepare_rollback(
                review.review_id,
                trusted_before={path: "answer=1\n"},
                trusted_current={path: "answer=3\n"},
            )

    def test_rollback_plan_id_is_deterministic_for_same_versions(self):
        first = self.plan()
        second = self.plan()
        self.assertEqual(first.plan_sha256, second.plan_sha256)

    def test_rollback_input_paths_are_restricted(self):
        with self.assertRaises(CodeProposalError):
            self.plan(before={**self.before, "../unsafe.py": "secret"})


if __name__ == "__main__":
    unittest.main()
