"""Regression test: Passenger lswsgi must not be invoked as Python CLI.

This test intentionally does not connect to any host or mutate server state.
"""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/zomorod-site-agent-cycle.yml"

class SiteAgentPythonGuard(unittest.TestCase):
    def test_passenger_launcher_not_used_as_cli(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("virtualenv/Saeit/3.10/bin/python", source)
        self.assertNotIn('python_path="$(awk', source)

    def test_existing_safety_guards_retained(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        for required in ("PINNED_CPANEL_RELAY=verified", "ZOMOROD_ROOT_APP_MAPPING=verified", "migrate --check", "cancel-in-progress: false"):
            with self.subTest(required=required):
                self.assertIn(required, source)

if __name__ == "__main__":
    unittest.main()
