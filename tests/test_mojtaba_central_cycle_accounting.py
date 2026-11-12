"""Operational cycle ledger regression: observations are not completed work."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from deploy import mojtaba_bot_cycle_coordinator as ledger


class CentralCycleAccountingTests(unittest.TestCase):
    def test_target_is_per_cycle(self):
        self.assertEqual(ledger.TARGET_BY_CYCLE, {"A": 20, "B": 20, "C": 20, "D": 20, "E": 50})

    def test_cross_cycle_reuse_of_run_id_is_refused(self):
        state = ledger.default_state()
        ledger.ensure_run(state, "A", "A-1")
        with self.assertRaises(SystemExit):
            ledger.ensure_run(state, "E", "A-1")

    def test_old_target_is_corrected_without_losing_recorded_actions(self):
        state = ledger.default_state()
        _, run = ledger.ensure_run(state, "A", "A-1")
        run["target"] = 50
        run["actions"]["historic"] = {"status": "blocked"}
        _, restored = ledger.ensure_run(state, "A", "A-1")
        self.assertEqual(restored["target"], 20)
        self.assertIn("historic", restored["actions"])

    def test_readonly_evidence_is_observation_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            file = str(Path(temp) / "cycles.json")
            common = dict(state=file, cycle="A", run_id="A-1",
                          action_id="read-1", item="artifact", kind="repo_readonly",
                          before="unknown", change="sha256", after="read-only",
                          evidence=["sha256:nonempty"])
            with self.assertRaises(SystemExit):
                ledger.cmd_record(SimpleNamespace(**common, status="success"))
            with redirect_stdout(io.StringIO()):
                ledger.cmd_record(SimpleNamespace(**common, status="observed"))
            output = io.StringIO()
            with redirect_stdout(output):
                ledger.cmd_summary(SimpleNamespace(state=file, cycle="A", run_id="A-1"))
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["observed"], 1)
            self.assertEqual(summary["success"], 0)
            self.assertEqual(summary["target"], 20)
            self.assertEqual(summary["remaining"], 20)
            self.assertFalse(summary["complete"])


if __name__ == "__main__":
    unittest.main()
