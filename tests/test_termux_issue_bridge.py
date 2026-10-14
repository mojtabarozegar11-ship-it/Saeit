import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from termux_bridge.issue_worker import (
    IssuesBridge, ISSUE_NUMBER, ISSUE_REPO, SAFE_CODES,
)
from termux_bridge.worker import BridgeError
from test_termux_bridge import NOW, request, seed_remote, cli


class MockGitHubIssues:
    def __init__(self):
        self.calls = []
        self.posted = []
        self.fail_auth = False
        self.fail_post = False

    def __call__(self, args):
        self.calls.append(args[:])
        if args[:2] == ["auth", "status"]:
            return not self.fail_auth
        if args[:2] == ["issue", "comment"]:
            if self.fail_post:
                return False
            self.posted.append(json.loads(Path(args[-1]).read_text()))
            return True
        raise AssertionError("Unexpected GitHub CLI call")

class IssueTransportTests(unittest.TestCase):
    def test_read_only_repo_can_submit_sanitized_issue_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("whoami_check"))
            gh = MockGitHubIssues()
            obj = IssuesBridge(
                Path(td) / "checkout", Path(td) / "local-only-state",
                remote=str(remote), clock=lambda: NOW, gh=gh,
            )
            old_sha = cli("--git-dir", remote, "rev-parse",
                          "feature/termux-safe-command-bridge-20261014")
            with patch("termux_bridge.issue_worker.run_allowlisted",
                       return_value={"ok": True, "code": "whoami_check_passed"}):
                result = obj.once()
            self.assertEqual(result, "ISSUE_RECEIPT_POSTED")
            self.assertEqual(len(gh.posted), 1)
            self.assertEqual(gh.posted[0]["code"], "whoami_check_passed")
            self.assertEqual(gh.posted[0]["command_id"], "probe-20261014")
            self.assertEqual(gh.posted[0]["type"], "saeit_termux_receipt_v1")
            self.assertEqual(
                cli("--git-dir", remote, "rev-parse",
                    "feature/termux-safe-command-bridge-20261014"), old_sha,
            )
            self.assertEqual(obj.once(), "ALREADY_HANDLED")
            self.assertEqual(len(gh.posted), 1)
            self.assertNotIn("private_android_username", json.dumps(gh.posted[0]))

    def test_issue_98_is_only_public_receipt_target(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("ping"))
            gh = MockGitHubIssues()
            obj = IssuesBridge(
                Path(td) / "checkout", Path(td) / "local-state",
                remote=str(remote), clock=lambda: NOW, gh=gh,
            )
            self.assertEqual(obj.once(), "ISSUE_RECEIPT_POSTED")
            self.assertEqual(gh.posted[0]["code"], "pong")
            issue_call = [c for c in gh.calls if c[:2] == ["issue","comment"]][0]
            self.assertEqual(issue_call[2], str(ISSUE_NUMBER))
            self.assertEqual(issue_call[3:5], ["--repo", ISSUE_REPO])
            self.assertEqual(ISSUE_NUMBER, 98)

    def test_missing_issue_auth_prevents_any_phone_command(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("whoami_check"))
            gh = MockGitHubIssues()
            gh.fail_auth = True
            obj = IssuesBridge(
                Path(td) / "checkout", Path(td) / "local-state",
                remote=str(remote), clock=lambda: NOW, gh=gh,
            )
            with patch("termux_bridge.issue_worker.run_allowlisted") as execute:
                with self.assertRaisesRegex(BridgeError, "authentication unavailable"):
                    obj.once()
            execute.assert_not_called()
            self.assertEqual(len(gh.posted), 0)

    def test_failed_issue_post_is_retried_without_reexecuting(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("whoami_check"))
            gh = MockGitHubIssues()
            gh.fail_post = True
            obj = IssuesBridge(
                Path(td) / "checkout", Path(td) / "local-state",
                remote=str(remote), clock=lambda: NOW, gh=gh,
            )
            with patch("termux_bridge.issue_worker.run_allowlisted",
                       return_value={"ok": True, "code": "whoami_check_passed"}) as execute:
                with self.assertRaisesRegex(BridgeError, "receipt submission failed"):
                    obj.once()
                state = json.loads(obj.state_file.read_text())
                self.assertEqual(state["pending"]["command_id"], "probe-20261014")
                gh.fail_post = False
                self.assertEqual(obj.once(), "ISSUE_RECEIPT_POSTED")
                self.assertEqual(obj.once(), "ALREADY_HANDLED")
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(gh.posted), 1)

    def test_illegal_action_never_reaches_gh(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("bash"))
            gh = MockGitHubIssues()
            obj = IssuesBridge(
                Path(td) / "checkout", Path(td) / "local-state",
                remote=str(remote), clock=lambda: NOW, gh=gh,
            )
            with self.assertRaisesRegex(BridgeError, "not allowlisted"):
                obj.once()
            self.assertEqual(gh.calls, [])

    def test_rejects_unexpected_receipt_code(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("ping"))
            gh = MockGitHubIssues()
            obj = IssuesBridge(
                Path(td) / "checkout", Path(td) / "local-state",
                remote=str(remote), clock=lambda: NOW, gh=gh,
            )
            with patch("termux_bridge.issue_worker.run_allowlisted",
                       return_value={"ok": True, "code": "full_private_stdout"}):
                with self.assertRaisesRegex(BridgeError, "unexpected action result"):
                    obj.once()
            self.assertEqual(gh.posted, [])
            self.assertNotIn("full_private_stdout", str(gh.calls))
            self.assertEqual(len(SAFE_CODES), 4)

if __name__ == "__main__":
    unittest.main()
