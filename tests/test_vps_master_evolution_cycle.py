"""Master capacity changes require diversified, verified executions."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/vps_master_evolution_cycle.py"
spec = importlib.util.spec_from_file_location("master_evolution", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EvolutionTests(unittest.TestCase):
    def fixture(self, temp, actions, *, previous_steps=2, failures=0):
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
            "completion_watermark": {"max_task_id": 0, "incomplete_task_ids": [], "complete": True},
        }))
        return db, state

    def test_repeated_verified_task_does_not_count_as_diverse_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_profit_optimize"] * 3)
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],1)
            self.assertEqual(out["recent_new_verified_action_types"],1)
            self.assertEqual(out["decision"],"rollback_repeated_or_unverified_completions")

    def test_diverse_verified_actions_allow_bounded_advance(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research","income_opportunity_score"])
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],3)
            self.assertEqual(out["recent_new_verified_action_types"],2)
            self.assertEqual(out["decision"],"diverse_verified_actions_expand_bounded_cycle")

    def test_failed_task_rolls_back_even_after_diverse_completions(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research","income_opportunity_score"],
                                     failures=1)
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],1)
            self.assertEqual(out["decision"],"rollback_to_conservative_after_regression")

    def test_old_queued_tasks_do_not_borrow_newer_verified_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["repeat", "repeat", "historical_a", "historical_b"]
            )
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET status='completed' WHERE id <= 4")
            prior = json.loads(state.read_text())
            prior["task_counts"]["completed"] = 2
            prior["completion_watermark"] = {
                "max_task_id": 4, "incomplete_task_ids": [1, 2], "complete": True
            }
            state.write_text(json.dumps(prior))
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["newly_completed_task_count"], 2)
            self.assertEqual(result["recent_new_verified_action_types"], 1)
            self.assertEqual(result["max_steps"], 1)

    def test_unverified_new_completions_never_borrow_old_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["new_a", "new_b", "historical_a", "historical_b"]
            )
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET output_data='{}' WHERE id <= 2")
            prior = json.loads(state.read_text())
            prior["task_counts"]["completed"] = 2
            prior["completion_watermark"] = {
                "max_task_id": 4, "incomplete_task_ids": [1, 2], "complete": True
            }
            state.write_text(json.dumps(prior))
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["newly_verified_task_count"], 0)
            self.assertEqual(result["recent_new_verified_action_types"], 0)
            self.assertEqual(result["max_steps"], 1)

    def test_legacy_state_bootstraps_before_allowing_capacity_growth(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["historical_a", "historical_b"]
            )
            prior = json.loads(state.read_text())
            del prior["completion_watermark"]
            state.write_text(json.dumps(prior))
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["max_steps"], 2)
            self.assertEqual(result["newly_completed_task_count"], 0)
            self.assertFalse(result["completion_identity_continuity"])
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','new_a',?)",
                    (json.dumps({"verified_effect": True}),)
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','new_b',?)",
                    (json.dumps({"verified_effect": True}),)
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["newly_completed_task_count"], 2)
            self.assertTrue(result["completion_identity_continuity"])
            self.assertEqual(result["max_steps"], 3)

    def test_successes_are_not_recounted_on_second_tick(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["a", "b"])
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["max_steps"], 3)
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["newly_completed_task_count"], 0)
            self.assertEqual(result["recent_new_verified_action_types"], 0)
            self.assertEqual(result["max_steps"], 3)



if __name__ == "__main__":
    unittest.main()
