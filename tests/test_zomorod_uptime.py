"""Fail-closed regression tests for non-destructive root health monitoring."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ops.zomorod_uptime import assess, probe


class MonitorTests(unittest.TestCase):
    def test_api_without_json_is_not_healthy(self):
        class Response:
            status = 200
            headers = {"Content-Type": "text/html"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b"<html>error</html>"
        with patch("ops.zomorod_uptime.urllib.request.urlopen", return_value=Response()):
            self.assertFalse(probe("/api/health/", "django", True)["ok"])

    def test_django_database_down_is_not_healthy(self):
        class Response:
            status = 200
            headers = {"Content-Type": "application/json"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b'{"status":"ok","database":"unavailable"}'
        with patch("ops.zomorod_uptime.urllib.request.urlopen", return_value=Response()):
            self.assertFalse(probe("/api/health/", "django", True)["ok"])

    def test_single_failed_sample_does_not_trigger_recovery(self):
        first = [{"path": "/", "ok": False}, {"path": "/api/health/", "ok": True}]
        second = [{"path": "/", "ok": True}, {"path": "/api/health/", "ok": True}]
        self.assertEqual(assess(first, second), (False, []))

    def test_double_failed_health_does_trigger_incident(self):
        rows = [{"path": "/", "ok": True}, {"path": "/api/health/", "ok": False}]
        self.assertEqual(assess(rows, rows), (True, ["/api/health/"]))

    def test_incomplete_samples_do_not_claim_confirmed_outage(self):
        first = [{"path": "/", "ok": False}, {"path": "/api/health/", "ok": True}]
        self.assertEqual(assess(first, []), (False, []))
        self.assertEqual(assess([], first), (False, []))

    def test_malformed_samples_are_ignored_without_a_crash(self):
        first = [None, {"path": "/", "ok": False}, {"ok": False}]
        second = [None, {"path": "/", "ok": False}, {"path": "/api/health/"}]
        self.assertEqual(assess(first, second), (True, ["/"]))
        self.assertEqual(assess([None, {"path": "/", "ok": False}], [None]), (False, []))

    def test_workflow_is_scoped_and_no_unconditional_restart(self):
        text = (Path(__file__).resolve().parents[1] /
                ".github/workflows/zomorod-503-watchdog.yml").read_text()
        self.assertIn("cron: '*/15 * * * *'", text)
        self.assertIn("confirmed_root_failure", text)
        self.assertIn("restart_requested", text)
        self.assertIn("PASSENGER_MAPPING=", text)
        self.assertNotIn("pkill", text)
        self.assertNotIn("rm -rf", text)


if __name__ == "__main__":
    unittest.main()
