"""Security and integration checks for AVA's in-memory code evolution."""

import unittest

from ava_core import (
    AvaRuntime, CheckEvidence, CodeEdit, CodeEvolutionDirector, CodeProposal,
    CodeProposalError,
)


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.original = "value = 1\n"
        self.changed = "value = 2\n"
        self.path = "ava_core/example.py"
        self.snapshot = {self.path: self.original}
        self.director = CodeEvolutionDirector(owner_id="owner")

    def proposal(self, edits=None, goal="Improve accuracy", rationale="Improve one internal function"):
        if edits is None:
            edits = (CodeEdit(self.path, self.director.digest(self.original), self.changed),)
        return CodeProposal(goal=goal, rationale=rationale, edits=edits)

    def review(self):
        return self.director.stage(self.proposal(), trusted_files=self.snapshot)

    def evidence(self, review, **override):
        defaults = dict(review_id=review.review_id, passed=True, isolated=True,
                        tests_run=12, runner="trusted-sandbox", details="12 checks passed")
        return CheckEvidence(**(defaults | override))

    def test_staging_contains_exact_diff_and_checksums(self):
        review = self.review()
        self.assertTrue(review.syntax_checked)
        self.assertEqual(review.owner_id, "owner")
        self.assertEqual(len(review.files), 1)
        self.assertIn("-value = 1", review.files[0].unified_diff)
        self.assertIn("+value = 2", review.files[0].unified_diff)
        self.assertEqual(review.files[0].old_sha256, self.director.digest(self.original))
        self.assertEqual(review.files[0].new_sha256, self.director.digest(self.changed))

    def test_staging_is_in_memory_and_does_not_change_source(self):
        self.review()
        self.assertEqual(self.snapshot[self.path], "value = 1\n")

    def test_same_proposal_is_idempotent(self):
        first = self.review()
        self.assertEqual(first.review_id, self.review().review_id)
        self.assertEqual(self.director.review_count(), 1)

    def test_different_owner_has_different_review_identity(self):
        first = self.review()
        other = CodeEvolutionDirector(owner_id="other")
        second = other.stage(self.proposal(), trusted_files=self.snapshot)
        self.assertNotEqual(first.review_id, second.review_id)
        self.assertIsNone(other.get_review(first.review_id))

    def test_stale_snapshot_rejected(self):
        edit = CodeEdit(self.path, self.director.digest("wrong"), self.changed)
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal((edit,)), trusted_files=self.snapshot)

    def test_new_python_file_requires_absent_base_digest(self):
        edit = CodeEdit("ava_core/new_capability.py", None, "def useful():\n    return 1\n")
        review = self.director.stage(self.proposal((edit,)), trusted_files=self.snapshot)
        self.assertIsNone(review.files[0].old_sha256)
        self.assertIn("/dev/null", review.files[0].unified_diff)

    def test_existing_file_cannot_be_misrepresented_as_new(self):
        edit = CodeEdit(self.path, None, self.changed)
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal((edit,)), trusted_files=self.snapshot)

    def test_unsafe_path_spellings_rejected(self):
        paths = ("../ava_core/example.py", "/ava_core/example.py",
                 "ava_core/../../secrets.py", ".github/workflows/publish.yml",
                 "ava_core/../tests/test_ava.py", "ava_core\\example.py",
                 "ava_core/.env", "tests/not_ava.py", "ava_core/example.py/evil")
        for path in paths:
            with self.subTest(path=path), self.assertRaises(CodeProposalError):
                self.director.stage(self.proposal((CodeEdit(path, None, self.changed),)),
                                    trusted_files=self.snapshot)

    def test_snapshot_itself_cannot_contain_unrelated_paths(self):
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal(), trusted_files={**self.snapshot, ".env": "TOKEN=secret"})

    def test_syntax_error_rejected_without_running_generated_code(self):
        edit = CodeEdit(self.path, self.director.digest(self.original), "def bad(:\n")
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal((edit,)), trusted_files=self.snapshot)

    def test_code_is_parsed_not_executed(self):
        marker = [False]
        # This code would fail if executed, but parsing must have no side effect.
        edit = CodeEdit(self.path, self.director.digest(self.original),
                        "raise RuntimeError('should not execute')\n")
        self.director.stage(self.proposal((edit,)), trusted_files=self.snapshot)
        self.assertFalse(marker[0])

    def test_empty_change_rejected(self):
        edit = CodeEdit(self.path, self.director.digest(self.original), self.original)
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal((edit,)), trusted_files=self.snapshot)

    def test_duplicate_paths_rejected(self):
        edit = CodeEdit(self.path, self.director.digest(self.original), self.changed)
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal((edit, edit)), trusted_files=self.snapshot)

    def test_many_edits_rejected(self):
        edits = tuple(CodeEdit(f"ava_core/new_{i}.py", None, "pass\n") for i in range(6))
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal(edits), trusted_files=self.snapshot)

    def test_oversize_source_rejected(self):
        edit = CodeEdit(self.path, self.director.digest(self.original), "x" * (64 * 1024 + 1))
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal((edit,)), trusted_files=self.snapshot)

    def test_missing_author_and_invalid_goals_refused(self):
        with self.assertRaises(PermissionError):
            self.director.propose("improve", trusted_files=self.snapshot)
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal(goal=" "), trusted_files=self.snapshot)
        with self.assertRaises(CodeProposalError):
            self.director.stage(self.proposal(rationale=""), trusted_files=self.snapshot)

    def test_missing_evidence_denies_handoff(self):
        review = self.review()
        with self.assertRaises(CodeProposalError):
            self.director.approve_handoff(review.review_id, evidence=None,
                                          authorize=lambda *_: True)

    def test_mismatched_evidence_denies_handoff(self):
        review = self.review()
        with self.assertRaises(CodeProposalError):
            self.director.approve_handoff(review.review_id,
                                          evidence=self.evidence(review, review_id="other"),
                                          authorize=lambda *_: True)

    def test_unisolated_or_failed_checks_deny_handoff(self):
        review = self.review()
        for override in ({"isolated": False}, {"passed": False},
                         {"tests_run": 0}, {"tests_run": True},
                         {"runner": ""}, {"details": ""}):
            with self.subTest(override=override), self.assertRaises(PermissionError):
                self.director.approve_handoff(review.review_id,
                                              evidence=self.evidence(review, **override),
                                              authorize=lambda *_: True)

    def test_independent_owner_approval_required(self):
        review = self.review()
        for authorize in (None, lambda *_: False, lambda *_: 1):
            with self.assertRaises(PermissionError):
                self.director.approve_handoff(review.review_id,
                                              evidence=self.evidence(review),
                                              authorize=authorize)

    def test_successful_handoff_does_not_commit_or_execute(self):
        review = self.review()
        bundle = self.director.approve_handoff(
            review.review_id, evidence=self.evidence(review),
            authorize=lambda owner, proposal: owner == "owner" and proposal == review,
        )
        self.assertEqual(bundle.review, review)
        self.assertEqual(self.snapshot[self.path], "value = 1\n")

    def test_runtime_uses_same_owner_for_code_evolution(self):
        proposer = lambda goal, files: self.proposal(goal=goal)
        runtime = AvaRuntime(owner_id="owner", brain=lambda _: "hello",
                             propose_goals=lambda _: (), code_proposer=proposer)
        review = runtime.propose_code_change("Improve accuracy", trusted_files=self.snapshot)
        self.assertEqual(review.owner_id, runtime.owner_id)
        self.assertEqual(runtime.status().code_reviews, 1)
        with self.assertRaises(PermissionError):
            runtime.approve_code_handoff(
                review.review_id, evidence=self.evidence(review),
                authorize=lambda owner, _: owner == "owner",
            )
        self.assertEqual(runtime.status().memory_items, 0)
        self.assertFalse(runtime.status().physical_actuation_enabled)


if __name__ == "__main__":
    unittest.main()
