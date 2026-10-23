"""Regression tests for Stage4 persisted retry eligibility and safety guards."""
import datetime as dt
import importlib.util
from pathlib import Path
import unittest


FILE = (Path(__file__).resolve().parents[1] / "scripts"
        / "factory_stage4_due_dispatch_20261023.py")
spec = importlib.util.spec_from_file_location("stage4_due_dispatch", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RetryEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 23, 12, tzinfo=dt.timezone.utc)

    def stage(self, date, status="waiting_for_evidence"):
        return {"validation": {"stage4_research": {
            "status": status, "next_retry_at": date}}}

    def test_due_and_overdue_are_eligible(self):
        self.assertEqual(module.due_retry(
            self.stage("2026-10-23T12:00:00+00:00"), self.now), self.now)
        self.assertLess(module.due_retry(
            self.stage("2026-10-22T01:00:00Z"), self.now), self.now)

    def test_future_retry_is_not_eligible(self):
        self.assertIsNone(module.due_retry(
            self.stage("2026-10-24T12:00:00+00:00"), self.now))

    def test_exhausted_capacity_cannot_be_bypassed(self):
        self.assertIsNone(module.due_retry(
            self.stage("2026-10-21T01:00:00Z", "capacity_exhausted"), self.now))

    def test_invalid_and_unsafe_timestamps_fail_closed(self):
        for stamp in (None, "", "sometime", "2026-10-22T12:00:00", "0" * 300):
            with self.subTest(stamp=stamp):
                self.assertIsNone(module.due_retry(self.stage(stamp), self.now))

    def test_invalid_metadata_fails_closed(self):
        for metadata in (None, [], {}, {"validation": "bad"},
                         {"validation": {"stage4_research": []}}):
            with self.subTest(metadata=metadata):
                self.assertIsNone(module.due_retry(metadata, self.now))


if __name__ == "__main__":
    unittest.main()
