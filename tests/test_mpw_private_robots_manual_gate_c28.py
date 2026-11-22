"""Regression guards for manual-only MojPlayWin private robot operations.

Source tests only: they must never connect to cPanel, start robots, or spend funds.
"""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / ".github/workflows" /
          "mpw-all-agents-private-activation.yml")


class MojPlayWinPrivateRobotsManualGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_no_automatic_live_install_or_execution(self):
        events = self.source.split("\npermissions:", 1)[0]
        self.assertEqual(events.splitlines()[-2:], ["on:", "  workflow_dispatch:"])
        for forbidden in ("\n  push:", "\n  schedule:", "\n  pull_request:",
                          "\n  issue_comment:", "\n  workflow_run:"):
            self.assertNotIn(forbidden, events)

    def test_live_audit_job_requires_explicit_main_dispatch(self):
        header = self.source.split("\n  audit:\n", 1)[1].split("\n    steps:", 1)[0]
        self.assertIn("github.repository == 'mojtabarozegar11-ship-it/Saeit'", header)
        self.assertIn("github.ref == 'refs/heads/main'", header)
        self.assertIn("github.event_name == 'workflow_dispatch'", header)
        self.assertIn("timeout-minutes: 7", header)

    def test_relay_identity_and_worker_verification_are_preserved(self):
        for marker in (
            "ref: 9dbc0e471a33179eb53a2445ae34ebdde20f495c",
            "StrictHostKeyChecking yes", "IdentitiesOnly yes",
            "ProxyJump saeit-vps", "Establish host-pinned private relay",
            "Install and actually run all five execution robots on cPanel",
            "Activate six private review and safety robots",
            "Execute actual safe MojPlayWin workers now under existing private locks",
            "Independently verify all eleven actual robots",
            "crontab", "if: always()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
