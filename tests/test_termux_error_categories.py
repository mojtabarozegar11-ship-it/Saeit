import subprocess
import unittest
from unittest.mock import patch

from termux_bridge.issue_worker import classify_gh_error, default_gh


class GitHubIssueDiagnosticsTests(unittest.TestCase):
    def test_missing_issue_write_permission(self):
        self.assertEqual(
            classify_gh_error("GraphQL: Resource not accessible by personal access token (HTTP 403)"),
            "ISSUES_TOKEN_MISSING_WRITE_PERMISSION",
        )

    def test_http_errors_redacted(self):
        examples = [
            ("HTTP 403: Unauthorized operation", "ISSUES_PERMISSION_DENIED_403"),
            ("HTTP 401: Bad credentials", "GITHUB_AUTHORIZATION_EXPIRED_401"),
            ("HTTP 404: Not Found", "GITHUB_ISSUE_NOT_FOUND_OR_INACCESSIBLE_404"),
            ("Could not resolve host", "GITHUB_NETWORK_UNAVAILABLE"),
            ("API rate limit exceeded", "GITHUB_RATE_LIMIT"),
            ("unknown response: SECRET_TOKEN_SHOULD_NOT_LEAK", "GITHUB_ISSUES_REJECTED_UNCLASSIFIED"),
        ]
        for raw, expected in examples:
            with self.subTest(raw=expected):
                self.assertEqual(classify_gh_error(raw), expected)

    def test_failed_issue_command_reports_only_sanitized_status(self):
        response = subprocess.CompletedProcess(
            ["gh", "issue", "comment"], 1,
            stdout=None, stderr="Secret Authorization TOKEN_DO_NOT_PRINT HTTP 403"
        )
        with patch("termux_bridge.issue_worker.subprocess.run", return_value=response) as run:
            with patch("termux_bridge.issue_worker.print") as output:
                self.assertFalse(default_gh(["issue", "comment", "98"]))
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.PIPE)
        printed = " ".join(" ".join(map(str, a.args)) for a in output.call_args_list)
        self.assertIn("GITHUB_ISSUE_DIAGNOSTIC=ISSUES_PERMISSION_DENIED_403", printed)
        self.assertNotIn("TOKEN_DO_NOT_PRINT", printed)

    def test_no_arbitrary_gh_calls(self):
        with self.assertRaisesRegex(Exception, "unexpected GitHub CLI"):
            default_gh(["api", "user"])


if __name__ == "__main__":
    unittest.main()
