"""End-to-end Linux isolation checks; nested test suite is synthetic and small."""

import os
from dataclasses import replace
import unittest
from unittest.mock import patch

from ava_core import (
    AvaRuntime, CodeEdit, CodeEvolutionDirector, CodeProposal,
    CodeProposalError, IsolatedReviewRunner,
    IsolationUnavailable,
)


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.path = "ava_core/example.py"
        self.original = "value = 1\n"
        self.changed = "value = 2\n"
        self.suite_path = "tests/test_ava_example.py"
        self.tree = {
            "ava_core/__init__.py": "",
            self.path: self.original,
            self.suite_path: (
                "import unittest\n"
                "from ava_core.example import value\n"
                "class Check(unittest.TestCase):\n"
                "    def test_value(self):\n"
                "        self.assertEqual(value, 2)\n"
            ),
        }
        self.director = CodeEvolutionDirector(owner_id="owner")
        self.runner = IsolatedReviewRunner(owner_id="owner", timeout_seconds=5)
        edit = CodeEdit(self.path, self.director.digest(self.original), self.changed)
        self.review = self.director.stage(
            CodeProposal(goal="Improve internal code", rationale="Correct a value", edits=(edit,)),
            trusted_files={self.path: self.original},
        )

    def test_real_isolated_suite_passes_on_changed_code(self):
        result = self.runner.evaluate(self.review, trusted_tree=self.tree)
        self.assertTrue(result.evidence.passed, result.stderr_excerpt)
        self.assertTrue(result.evidence.isolated)
        self.assertEqual(result.evidence.tests_run, 1)
        self.assertEqual(result.exit_code, 0)

    def test_host_tree_is_unchanged_after_isolated_run(self):
        self.runner.evaluate(self.review, trusted_tree=self.tree)
        self.assertEqual(self.tree[self.path], self.original)

    def test_temporary_files_are_removed_after_run(self):
        result = self.runner.evaluate(self.review, trusted_tree=self.tree)
        self.assertTrue(result.staged_files_removed)

    def test_failing_suite_returns_failed_evidence(self):
        tree = dict(self.tree)
        tree[self.suite_path] = tree[self.suite_path].replace("value, 2", "value, 3")
        result = self.runner.evaluate(self.review, trusted_tree=tree)
        self.assertFalse(result.evidence.passed)
        self.assertNotEqual(result.exit_code, 0)
        with self.assertRaises(PermissionError):
            self.director.approve_handoff(
                self.review.review_id, evidence=result.evidence,
                authorize=lambda *_: True,
            )

    def test_no_network_inside_real_sandbox(self):
        tree = dict(self.tree)
        tree[self.suite_path] += (
            "    def test_external_network_unreachable(self):\n"
            "        import socket\n"
            "        with socket.socket() as s:\n"
            "            self.assertNotEqual(s.connect_ex(('1.1.1.1', 53)), 0)\n"
        )
        result = self.runner.evaluate(self.review, trusted_tree=tree)
        self.assertTrue(result.evidence.passed, result.stderr_excerpt)
        self.assertEqual(result.evidence.tests_run, 2)

    def test_project_tree_is_read_only_in_sandbox(self):
        tree = dict(self.tree)
        tree[self.suite_path] += (
            "    def test_readonly_source(self):\n"
            "        with self.assertRaises(OSError):\n"
            "            open('ava_core/example.py', 'w')\n"
        )
        result = self.runner.evaluate(self.review, trusted_tree=tree)
        self.assertTrue(result.evidence.passed, result.stderr_excerpt)

    def test_host_etc_not_visible_inside_sandbox(self):
        tree = dict(self.tree)
        tree[self.suite_path] += (
            "    def test_host_config_not_mounted(self):\n"
            "        import os\n"
            "        self.assertFalse(os.path.exists('/etc/passwd'))\n"
        )
        result = self.runner.evaluate(self.review, trusted_tree=tree)
        self.assertTrue(result.evidence.passed, result.stderr_excerpt)

    def test_stale_version_rejected_before_execution(self):
        tree = dict(self.tree)
        tree[self.path] = "value = 999\n"
        with self.assertRaises(CodeProposalError):
            self.runner.evaluate(self.review, trusted_tree=tree)

    def test_unknown_or_unsafe_snapshot_paths_rejected(self):
        tree = dict(self.tree)
        tree["private/.env"] = "SECRET=do-not-mount"
        with self.assertRaises(CodeProposalError):
            self.runner.evaluate(self.review, trusted_tree=tree)

    def test_other_owner_cannot_evaluate_review(self):
        foreign = IsolatedReviewRunner(owner_id="someone-else")
        with self.assertRaises(PermissionError):
            foreign.evaluate(self.review, trusted_tree=self.tree)

    def test_restricted_execution_timeout_fails(self):
        tree = dict(self.tree)
        tree[self.suite_path] += (
            "    def test_infinite_loop(self):\n"
            "        while True: pass\n"
        )
        runner = IsolatedReviewRunner(owner_id="owner", timeout_seconds=1)
        result = runner.evaluate(self.review, trusted_tree=tree)
        self.assertFalse(result.evidence.passed)
        self.assertTrue(result.staged_files_removed)

    def test_runtime_integration_and_handoff(self):
        runtime = AvaRuntime(owner_id="owner", brain=lambda _: "hello",
                             propose_goals=lambda _: (), review_runner=self.runner)
        own_review = runtime.review_code_change(
            CodeProposal(
                goal="Improve internal code", rationale="Correct a value",
                edits=(CodeEdit(self.path, self.director.digest(self.original), self.changed),),
            ), trusted_files={self.path: self.original},
        )
        result = runtime.evaluate_code_change(own_review.review_id, trusted_tree=self.tree)
        self.assertTrue(runtime.status().isolated_review_runner_configured)
        self.assertTrue(result.evidence.passed, result.stderr_excerpt)
        bundle = runtime.approve_code_handoff(
            own_review.review_id, evidence=result.evidence,
            authorize=lambda owner, review: owner == "owner" and review.review_id == own_review.review_id,
        )
        self.assertEqual(bundle.review.review_id, own_review.review_id)
        self.assertEqual(self.tree[self.path], self.original)

    def test_runtime_default_denies_execution_without_runner(self):
        runtime = AvaRuntime(owner_id="owner", brain=lambda _: "hello",
                             propose_goals=lambda _: ())
        with self.assertRaises(PermissionError):
            runtime.evaluate_code_change(self.review.review_id, trusted_tree=self.tree)

    def test_zero_tests_cannot_pass(self):
        tree = dict(self.tree)
        tree[self.suite_path] = "# Empty test module is not evidence\n"
        result = self.runner.evaluate(self.review, trusted_tree=tree)
        self.assertFalse(result.evidence.passed)
        self.assertEqual(result.evidence.tests_run, 0)

    def test_missing_trusted_suite_rejected(self):
        tree = {k: v for k, v in self.tree.items() if k != self.suite_path}
        with self.assertRaises(CodeProposalError):
            self.runner.evaluate(self.review, trusted_tree=tree)

    def test_tampered_review_source_digest_rejected(self):
        wrong_file = replace(self.review.files[0], new_sha256="0" * 64)
        altered_review = replace(self.review, files=(wrong_file,))
        with self.assertRaises(CodeProposalError):
            self.runner.evaluate(altered_review, trusted_tree=self.tree)

    def test_unavailable_namespace_tool_fails_closed(self):
        with patch.object(self.runner, "_validate_runner", side_effect=IsolationUnavailable("missing")):
            with self.assertRaises(IsolationUnavailable):
                self.runner.evaluate(self.review, trusted_tree=self.tree)

    def test_runtime_refuses_runner_from_other_owner(self):
        with self.assertRaises(PermissionError):
            AvaRuntime(owner_id="owner", brain=lambda _: "hello",
                       propose_goals=lambda _: (),
                       review_runner=IsolatedReviewRunner(owner_id="other"))

    def test_host_environment_secrets_are_not_inherited(self):
        tree = dict(self.tree)
        tree[self.suite_path] += (
            "    def test_host_secret_not_in_environment(self):\n"
            "        import os\n"
            "        self.assertNotIn('AVA_HOST_SECRET', os.environ)\n"
        )
        with patch.dict(os.environ, {"AVA_HOST_SECRET": "test-sensitive-placeholder"}):
            result = self.runner.evaluate(self.review, trusted_tree=tree)
        self.assertTrue(result.evidence.passed, result.stderr_excerpt)

    def test_sandbox_tmp_writable_without_writing_host_tree(self):
        tree = dict(self.tree)
        tree[self.suite_path] += (
            "    def test_private_scratch(self):\n"
            "        with open('/tmp/ava-scratch.txt', 'w') as handle:\n"
            "            handle.write('isolated')\n"
            "        with open('/tmp/ava-scratch.txt') as handle:\n"
            "            self.assertEqual(handle.read(), 'isolated')\n"
        )
        result = self.runner.evaluate(self.review, trusted_tree=tree)
        self.assertTrue(result.evidence.passed, result.stderr_excerpt)

    def test_bad_resource_limits_are_rejected(self):
        for time_limit, memory_mb in ((0, 512), (61, 512), (5, 128), (5, 4096), (True, 512)):
            with self.subTest(time_limit=time_limit, memory_mb=memory_mb), self.assertRaises(ValueError):
                IsolatedReviewRunner(owner_id="owner", timeout_seconds=time_limit,
                                     memory_limit_mb=memory_mb)


if __name__ == "__main__":
    unittest.main()
