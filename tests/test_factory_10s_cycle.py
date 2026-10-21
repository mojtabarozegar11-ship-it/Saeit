import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "factory_10s_cycle.py"
spec = importlib.util.spec_from_file_location("factory_10s_cycle_under_test", SOURCE)
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)

class TenSecondCycleTests(unittest.TestCase):
    def test_fixed_private_intervals_and_task_budget(self):
        self.assertEqual(tuple(cycle.TASK_INTERVALS), (
            "repair", "production_evolution", "generations", "code_improvement"))
        self.assertTrue(all(60 <= seconds <= 600 for seconds in cycle.TASK_INTERVALS.values()))
        self.assertTrue(all(seconds <= 220 for seconds in cycle.TIMEOUTS.values()))

    def test_new_queue_starts_with_repair_and_respects_backoff(self):
        self.assertEqual(cycle.choose_due({}, 1000), "repair")
        now = 1000
        started = {task: now for task in cycle.TASK_INTERVALS}
        self.assertIsNone(cycle.choose_due(started, now + 9))
        self.assertEqual(cycle.choose_due(started, now + 60), "repair")
        started["repair"] = now + 120
        self.assertIsNone(cycle.choose_due(started, now + 61))
        self.assertEqual(cycle.choose_due(started, now + 120), "production_evolution")

    def test_atomic_private_state_and_schema_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as scratch:
            p = Path(scratch) / "state.json"
            cycle.atomic_json(p, {"schema": cycle.SCHEMA, "ticks": 3, "last_started": {}})
            self.assertEqual(cycle.load_state(p)["ticks"], 3)
            cycle.atomic_json(p, {"schema": "unknown", "ticks": 3, "last_started": {}})
            with self.assertRaises(RuntimeError):
                cycle.load_state(p)

    def test_no_public_release_or_1000_score_bypass(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"quality_1000_certified": False', source)
        self.assertIn('"public_release_authorized": False', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system(", source)

if __name__ == "__main__":
    unittest.main()
