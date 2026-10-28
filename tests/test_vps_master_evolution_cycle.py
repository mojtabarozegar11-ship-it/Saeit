"""Master production stays capped at one step despite verified progress."""
import importlib.util
import json
import os
import stat
from pathlib import Path
import sqlite3
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/vps_master_evolution_cycle.py"
spec = importlib.util.spec_from_file_location("master_evolution", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EvolutionTests(unittest.TestCase):
    def fixture(self, temp, actions, *, previous_steps=1, failures=0):
        root = Path(temp)
        db = root / "master.sqlite3"
        state = root / "evolution.json"
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE core_agent (id INTEGER PRIMARY KEY, code TEXT, active INTEGER)")
            conn.execute("CREATE TABLE core_agenttask (id INTEGER PRIMARY KEY, agent_id INTEGER, status TEXT, action_type TEXT, output_data TEXT)")
            conn.execute("INSERT INTO core_agent VALUES (1,'economic-master-agent',1)")
            for action in actions:
                conn.execute("INSERT INTO core_agenttask(agent_id,status,action_type,output_data) VALUES (1,'completed',?,?)",
                             (action,json.dumps({"verified_effect":True})))
            for _ in range(failures):
                conn.execute("INSERT INTO core_agenttask(agent_id,status,action_type,output_data) VALUES (1,'failed','example','{}')")
        state.write_text(json.dumps({
            "schema": "saeit.master.evolution.v1",
            "max_steps": previous_steps, "revision": 1,
            "task_counts": {"completed": 0,"failed": 0,"blocked": 0},
        }))
        return db, state

    def test_repeated_verified_task_does_not_count_as_diverse_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_profit_optimize"] * 3)
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],1)
            self.assertEqual(out["recent_new_verified_action_types"],1)
            self.assertEqual(out["decision"],"hold_single_step_no_verified_diversity")

    def test_diverse_verified_actions_do_not_expand_production_volume(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research","income_opportunity_score"])
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],1)
            self.assertEqual(out["hard_max_steps_cap"],1)
            self.assertFalse(out["volume_scaling_enabled"])
            self.assertEqual(out["recent_new_verified_action_types"],2)
            self.assertEqual(out["decision"],"hold_single_step_after_verified_progress")

    def test_legacy_expanded_state_is_reduced_to_one_step(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research", "income_opportunity_score"],
                                     previous_steps=3)
            mod.evaluate(db, state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"], 1)
            self.assertEqual(out["decision"], "rollback_to_single_step_volume_cap")

    def test_existing_nonprivate_directory_fails_without_chmod_side_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, [])
            os.chmod(temp, 0o755)
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_STATE_DIR_NOT_PRIVATE"):
                mod.evaluate(db, state)
            self.assertEqual(stat.S_IMODE(Path(temp).stat().st_mode), 0o755)
            self.assertEqual(json.loads(state.read_text())["revision"], 1)

    def test_symlinked_state_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "private"
            private.mkdir(mode=0o700)
            db, _ = self.fixture(str(private), [])
            alias = root / "alias"
            alias.symlink_to(private, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_STATE_PARENT_SYMLINK"):
                mod.evaluate(db, alias / "evolution.json")
            self.assertEqual(json.loads((private / "evolution.json").read_text())["revision"], 1)

    def test_failed_task_rolls_back_even_after_diverse_completions(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research","income_opportunity_score"],
                                     failures=1)
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],1)
            self.assertEqual(out["decision"],"hold_single_step_after_regression")


if __name__ == "__main__":
    unittest.main()
