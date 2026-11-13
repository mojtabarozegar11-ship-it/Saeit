"""Master runs up to 20 serial tasks without increasing product volume."""
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
            db, state = self.fixture(temp, ["income_profit_optimize"] * 3, previous_steps=20)
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],20)
            self.assertEqual(out["recent_new_verified_action_types"],1)
            self.assertEqual(out["decision"],"hold_serial_chain_no_verified_diversity")

    def test_diverse_verified_actions_do_not_expand_product_volume(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research","income_opportunity_score"], previous_steps=20)
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],20)
            self.assertEqual(out["hard_max_steps_cap"],20)
            self.assertFalse(out["volume_scaling_enabled"])
            self.assertEqual(out["recent_new_verified_action_types"],2)
            self.assertEqual(out["decision"],"hold_serial_chain_after_verified_progress")

    def test_old_verified_actions_are_not_recounted_when_new_task_is_unverified(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_profit_optimize',?)",
                    (json.dumps({"verified_effect": False}),)
                )
            previous = json.loads(state.read_text())
            previous["task_counts"]["completed"] = 2
            previous["last_completed_task_id"] = 2
            state.write_text(json.dumps(previous))
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["delta"]["completed_tasks_net_change"], 1)
            self.assertEqual(result["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(result["recent_new_verified_action_types"], 0)
            self.assertEqual(result["decision"], "hold_serial_chain_until_verified_progress")
            self.assertEqual(result["last_completed_task_id"], 3)

    def test_only_new_verified_action_is_counted_after_cursor(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            previous = json.loads(state.read_text())
            previous["task_counts"]["completed"] = 1
            previous["last_completed_task_id"] = 1
            state.write_text(json.dumps(previous))
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["delta"]["verified_completed_tasks"], 1)
            self.assertEqual(result["recent_new_verified_action_types"], 1)
            self.assertEqual(result["decision"], "hold_serial_chain_until_verified_progress")
            mod.evaluate(db, state)
            second = json.loads(state.read_text())
            self.assertEqual(second["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(second["last_completed_task_id"], 2)

    def test_legacy_nonzero_completed_history_abstains_without_cursor(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            previous = json.loads(state.read_text())
            previous["task_counts"]["completed"] = 2
            state.write_text(json.dumps(previous))
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertFalse(result["previous_completed_cursor_trusted"])
            self.assertEqual(result["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(result["recent_new_verified_action_types"], 0)

    def test_rejects_invalid_stored_task_cursor_without_modifying_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"])
            previous = json.loads(state.read_text())
            previous["last_completed_task_id"] = True
            state.write_text(json.dumps(previous))
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "INVALID_PREVIOUS_EVOLUTION_TASK_CURSOR"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_legacy_state_migrates_to_serial_task_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research", "income_opportunity_score"],
                                     previous_steps=3)
            mod.evaluate(db, state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"], 20)
            self.assertEqual(out["decision"], "enable_serial_chain_up_to_20")

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

    def test_rejects_database_with_symlinked_ancestor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "actual"
            private.mkdir()
            db, state = self.fixture(str(private), [])
            alias = root / "db-alias"
            alias.symlink_to(private, target_is_directory=True)
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_PRIVATE_DB_NOT_FOUND"):
                mod.evaluate(alias / db.name, state)
            self.assertEqual(state.read_bytes(), before)

    def test_rejects_state_with_symlinked_grandparent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "actual" / "nested"
            private.mkdir(parents=True)
            db, state = self.fixture(str(private), [])
            alias = root / "state-alias"
            alias.symlink_to(root / "actual", target_is_directory=True)
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_STATE_PARENT_SYMLINK"):
                mod.evaluate(db, alias / "nested" / state.name)
            self.assertEqual(state.read_bytes(), before)

    def test_rejects_invalid_state_json_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, [])
            state.write_bytes(b"{broken")
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_STATE_INVALID_JSON"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_rejects_invalid_old_counts_without_replacing_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"])
            data = json.loads(state.read_text())
            data["task_counts"]["completed"] = True
            state.write_text(json.dumps(data))
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_PREVIOUS_COUNTS_INVALID"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_rejects_cursor_ahead_of_restored_database(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"])
            data = json.loads(state.read_text())
            data["last_completed_task_id"] = 100
            state.write_text(json.dumps(data))
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_TASK_CURSOR_AHEAD"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_rejects_invalid_stored_policy_and_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, [])
            for key, value, expected in (
                ("max_steps", "20", "INVALID_PREVIOUS_EVOLUTION_POLICY"),
                ("revision", True, "MASTER_EVOLUTION_PREVIOUS_REVISION_INVALID"),
            ):
                data = json.loads(state.read_text())
                data[key] = value
                state.write_text(json.dumps(data))
                before = state.read_bytes()
                with self.assertRaisesRegex(RuntimeError, expected):
                    mod.evaluate(db, state)
                self.assertEqual(state.read_bytes(), before)
                data[key] = 1
                state.write_text(json.dumps(data))

    def test_rejects_oversized_previous_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, [])
            state.write_bytes(b"x" * (mod.MAX_STATE_BYTES + 1))
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_STATE_UNSAFE"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_rejects_truncated_audit_window_without_false_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"] * 130, previous_steps=20)
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_NEW_TASKS_EXCEED_AUDIT_WINDOW"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_corrected_corrupt_state_can_resume_without_bypassing_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            baseline = state.read_bytes()
            state.write_text("not-json")
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_STATE_INVALID_JSON"):
                mod.evaluate(db, state)
            state.write_bytes(baseline)
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["delta"]["verified_completed_tasks"], 1)
            self.assertFalse(result["commercial_publication_enabled"])
            self.assertFalse(result["financial_actions_enabled"])

    def test_failed_task_rolls_back_even_after_diverse_completions(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research","income_opportunity_score"],
                                     previous_steps=20, failures=1)
            mod.evaluate(db,state)
            out = json.loads(state.read_text())
            self.assertEqual(out["max_steps"],1)
            self.assertEqual(out["decision"],"limit_serial_steps_after_regression")


if __name__ == "__main__":
    unittest.main()
