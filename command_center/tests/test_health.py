import unittest
from datetime import datetime, timedelta, timezone
from command_center.health import Observation, effective_state, summarize, progress

class HealthTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 10, tzinfo=timezone.utc)

    def item(self, state="healthy", age=0):
        return Observation("factory", state, self.now - timedelta(seconds=age), "db", "event-123")

    def test_empty_is_unknown(self):
        self.assertEqual(summarize([], self.now)["overall"], "unknown")

    def test_stale_not_healthy(self):
        self.assertEqual(effective_state(self.item(age=301), self.now), "stale")

    def test_failure_wins(self):
        self.assertEqual(summarize([self.item(), self.item("failed")], self.now)["overall"], "failed")

    def test_missing_evidence_rejected(self):
        with self.assertRaises(ValueError):
            Observation("factory", "healthy", self.now, "", "")

    def test_verified_progress(self):
        self.assertEqual(progress(8, 10, 5)["verified_percent"], 50)
        self.assertEqual(progress(8, 10, 5)["unverified"], 3)

    def test_unknown_total(self):
        self.assertIsNone(progress(0, 0, 0)["verified_percent"])

if __name__ == "__main__":
    unittest.main()
