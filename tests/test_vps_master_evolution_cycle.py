"""Master runs up to 20 serial tasks without increasing product volume."""
import importlib.util
import io
import json
import os
import shutil
import stat
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/vps_master_evolution_cycle.py"
spec = importlib.util.spec_from_file_location("master_evolution", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EvolutionTests(unittest.TestCase):
    @staticmethod
    def proof():
        # Match economic TaskRuntime's internal completion gate. This is
        # fixture evidence, NOT a claim of independent external verification.
        return {
            "verified_effect": True,
            "action_performed": "Inspected and recorded an internal task result.",
            "evidence": {"kind": "fixture_measurement", "value": "test row"},
        }

    def fixture(self, temp, actions, *, previous_steps=1, failures=0):
        root = Path(temp)
        db = root / "master.sqlite3"
        state = root / "evolution.json"
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE core_agent (id INTEGER PRIMARY KEY, code TEXT, active INTEGER)")
            conn.execute("CREATE TABLE core_agenttask (id INTEGER PRIMARY KEY, agent_id INTEGER, status TEXT, action_type TEXT, output_data TEXT, execution_id TEXT DEFAULT 'fixture-execution', attempt_count INTEGER DEFAULT 1)")
            conn.execute("INSERT INTO core_agent VALUES (1,'economic-master-agent',1)")
            for action in actions:
                conn.execute("INSERT INTO core_agenttask(agent_id,status,action_type,output_data) VALUES (1,'completed',?,?)",
                             (action,json.dumps(self.proof())))
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

    def test_late_older_task_completion_is_counted_once(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_opportunity_score',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            first = json.loads(state.read_text())
            self.assertEqual(first["pending_prior_ids"], [2])
            self.assertEqual(first["last_completed_task_id"], 3)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            second = json.loads(state.read_text())
            self.assertEqual(second["delta"]["verified_completed_tasks"], 1)
            self.assertEqual(second["late_verified_completed_tasks"], 1)
            self.assertEqual(second["late_completed_tasks"], 1)
            self.assertEqual(second["pending_prior_ids"], [])
            self.assertEqual(second["last_completed_task_id"], 3)
            mod.evaluate(db, state)
            third = json.loads(state.read_text())
            self.assertEqual(third["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(third["late_verified_completed_tasks"], 0)

    def test_two_distinct_late_tasks_count_as_verified_diverse_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                for action in ("income_profit_optimize", "income_opportunity_score"):
                    conn.execute(
                        "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                        "VALUES (1,'queued',?,'{}')", (action,)
                    )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_market_research',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["pending_prior_ids"], [2, 3])
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? "
                    "WHERE id IN (2,3)", (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["delta"]["verified_completed_tasks"], 2)
            self.assertEqual(result["late_verified_completed_tasks"], 2)
            self.assertEqual(result["recent_new_verified_action_types"], 2)
            self.assertEqual(result["decision"], "hold_serial_chain_after_verified_progress")
            self.assertFalse(result["financial_actions_enabled"])

    def test_late_unverified_completion_never_creates_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_market_research',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps({"verified_effect": False}),)
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["late_completed_tasks"], 1)
            self.assertEqual(result["late_verified_completed_tasks"], 0)
            self.assertEqual(result["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(result["pending_prior_ids"], [])
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            # A completed task's outcome cannot be upgraded retroactively:
            # the previously stored snapshot fingerprint must catch tampering.
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_legacy_state_does_not_credit_unproven_old_pending_tasks(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_opportunity_score',?)",
                    (json.dumps(self.proof()),)
                )
            previous = json.loads(state.read_text())
            previous["last_completed_task_id"] = 3
            previous["task_counts"]["completed"] = 2
            state.write_text(json.dumps(previous))
            mod.evaluate(db, state)
            first = json.loads(state.read_text())
            self.assertFalse(first["previous_pending_tracking_available"])
            self.assertEqual(first["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(first["pending_prior_ids"], [])
            self.assertEqual(first["suppressed_unproven_prior_pending_count"], 1)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            second = json.loads(state.read_text())
            self.assertTrue(second["previous_pending_tracking_available"])
            self.assertEqual(second["late_verified_completed_tasks"], 0)
            self.assertEqual(second["delta"]["verified_completed_tasks"], 0)

    def test_contiguous_129_new_completions_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"] * 129, previous_steps=20)
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_NEW_TASKS_EXCEED_AUDIT_WINDOW"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_exactly_128_contiguous_new_completions_are_accounted_for(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"] * 128, previous_steps=20)
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["delta"]["verified_completed_tasks"], 128)
            self.assertEqual(result["last_completed_task_id"], 128)
            self.assertEqual(result["recent_new_verified_action_types"], 1)

    def test_invalid_or_duplicate_pending_ids_are_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            original = json.loads(state.read_text())
            original["last_completed_task_id"] = 1
            for bad in (True, "1", [True], [0], [1, 1], [3, 2]):
                data = dict(original, pending_prior_ids=bad)
                state.write_text(json.dumps(data))
                before = state.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_PENDING_IDS_INVALID"):
                    mod.evaluate(db, state)
                self.assertEqual(state.read_bytes(), before)

    def test_missing_previously_tracked_pending_task_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_opportunity_score',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute("DELETE FROM core_agenttask WHERE id=2")
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_PREVIOUS_PENDING_TASK_DISAPPEARED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_pending_tracking_capacity_failure_preserves_previous_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                for _ in range(3):
                    conn.execute(
                        "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                        "VALUES (1,'queued','income_profit_optimize','{}')"
                    )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_market_research',?)",
                    (json.dumps(self.proof()),)
                )
            before = state.read_bytes()
            with mock.patch.object(mod, "MAX_TRACKED_PENDING_TASKS", 2):
                with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_PENDING_TRACKING_LIMIT_EXCEEDED"):
                    mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_previously_completed_older_task_cannot_be_recredited_after_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["last_completed_task_id"], 2)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='queued',output_data='{}' WHERE id=1"
                )
            mod.evaluate(db, state)
            reopened = json.loads(state.read_text())
            self.assertEqual(reopened["pending_prior_ids"], [])
            self.assertEqual(reopened["suppressed_unproven_prior_pending_count"], 1)
            self.assertEqual(reopened["max_steps"], 1)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=1",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            final = json.loads(state.read_text())
            self.assertEqual(final["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(final["late_verified_completed_tasks"], 0)
            self.assertEqual(final["last_completed_task_id"], 2)

    def test_reopened_watermark_task_retains_monotone_cursor_and_restricts_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            mod.evaluate(db, state)
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET status='queued',output_data='{}' WHERE id=2")
            mod.evaluate(db, state)
            reopened = json.loads(state.read_text())
            self.assertTrue(reopened["watermark_task_reopened"])
            self.assertEqual(reopened["last_completed_task_id"], 2)
            self.assertEqual(reopened["max_steps"], 1)
            self.assertEqual(reopened["pending_prior_ids"], [])
            self.assertEqual(reopened["delta"]["verified_completed_tasks"], 0)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertFalse(result["watermark_task_reopened"])
            self.assertEqual(result["last_completed_task_id"], 2)
            self.assertEqual(result["delta"]["verified_completed_tasks"], 0)

    def test_pending_task_credited_once_remains_ineligible_after_subsequent_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_opportunity_score',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["pending_prior_ids"], [2])
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["late_verified_completed_tasks"], 1)
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET status='queued',output_data='{}' WHERE id=2")
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["pending_prior_ids"], [])
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["delta"]["verified_completed_tasks"], 0)

    def test_new_pending_above_cursor_remains_eligible_for_late_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_opportunity_score',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            mid = json.loads(state.read_text())
            self.assertEqual(mid["pending_prior_ids"], [2])
            self.assertEqual(mid["suppressed_unproven_prior_pending_count"], 0)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["late_verified_completed_tasks"], 1)

    def test_tracked_pending_survives_high_watermark_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_opportunity_score',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["pending_prior_ids"], [2])
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='queued',output_data='{}' WHERE id=3"
                )
            mod.evaluate(db, state)
            reopened = json.loads(state.read_text())
            self.assertTrue(reopened["watermark_task_reopened"])
            self.assertEqual(reopened["pending_prior_ids"], [2])
            self.assertEqual(reopened["suppressed_unproven_prior_pending_count"], 1)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["late_verified_completed_tasks"], 1)
            self.assertEqual(result["delta"]["verified_completed_tasks"], 1)
            self.assertEqual(result["last_completed_task_id"], 3)

    def test_completed_guard_detects_evidence_rewrite_without_losing_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET output_data=? WHERE id=1",
                    (json.dumps({"verified_effect": False}),)
                )
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_completed_guard_detects_execution_id_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET execution_id='changed' WHERE id=1")
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_completed_guard_detects_action_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET action_type='income_profit_optimize' WHERE id=1")
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_completed_guard_detects_attempt_number_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET attempt_count=2 WHERE id=1")
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_newer_completed_task_cannot_mask_reopening_of_watermark(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            mod.evaluate(db, state)
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET status='queued' WHERE id=2")
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_profit_optimize',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["delta"]["completed_tasks_net_change"], 0)
            self.assertTrue(result["watermark_task_reopened"])
            self.assertEqual(result["guarded_reopened_task_count"], 1)
            self.assertEqual(result["max_steps"], 1)
            self.assertEqual(result["decision"], "limit_serial_steps_after_regression")
            self.assertEqual(result["delta"]["verified_completed_tasks"], 1)

    def test_newer_completion_cannot_mask_reopening_older_guarded_task(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            mod.evaluate(db, state)
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET status='queued' WHERE id=1")
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_profit_optimize',?)",
                    (json.dumps(self.proof()),)
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["delta"]["completed_tasks_net_change"], 0)
            self.assertFalse(result["watermark_task_reopened"])
            self.assertEqual(result["guarded_reopened_task_count"], 1)
            self.assertEqual(result["max_steps"], 1)
            self.assertEqual(result["delta"]["verified_completed_tasks"], 1)

    def test_missing_guarded_task_rejected_without_state_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute("DELETE FROM core_agenttask WHERE id=1")
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_profit_optimize',?)",
                    (json.dumps(self.proof()),)
                )
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_GUARD_TASK_MISSING"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_invalid_completed_guard_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            data = json.loads(state.read_text())
            data["completed_guard"]["1"] = "not-a-valid-sha256"
            state.write_text(json.dumps(data))
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_GUARD_INVALID"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_forged_but_valid_guard_digest_fails_at_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            data = json.loads(state.read_text())
            data["completed_guard"]["1"] = "f" * 64
            state.write_text(json.dumps(data))
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_legacy_state_creates_guard_without_recrediting_history(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            data = json.loads(state.read_text())
            data["last_completed_task_id"] = 2
            data["task_counts"]["completed"] = 2
            state.write_text(json.dumps(data))
            mod.evaluate(db, state)
            first = json.loads(state.read_text())
            self.assertFalse(first["previous_completed_guard_available"])
            self.assertEqual(first["previous_completed_guard_rows_checked"], 0)
            self.assertEqual(first["delta"]["verified_completed_tasks"], 0)
            self.assertEqual(len(first["completed_guard"]), 2)
            mod.evaluate(db, state)
            second = json.loads(state.read_text())
            self.assertTrue(second["previous_completed_guard_available"])
            self.assertEqual(second["previous_completed_guard_rows_checked"], 2)
            self.assertEqual(second["delta"]["verified_completed_tasks"], 0)

    def test_check_only_calculates_policy_without_changing_saved_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(
                temp, ["income_market_research", "income_opportunity_score"],
                previous_steps=20
            )
            # The cron evaluator first persists and privately locks down the
            # baseline; direct check-only against the legacy fixture is unsafe.
            mod.evaluate(db, state)
            before = state.read_bytes()
            transcript = io.StringIO()
            with redirect_stdout(transcript):
                mod.evaluate(db, state, check_only=True)
            self.assertEqual(state.read_bytes(), before)
            self.assertIn("MASTER_EVOLUTION_CHECK_ONLY=true", transcript.getvalue())
            self.assertIn("MASTER_EVOLUTION_MAX_STEPS=20", transcript.getvalue())
            self.assertIn("MASTER_EVOLUTION_PREVIOUS_MAX_STEPS=20", transcript.getvalue())

    def test_check_only_never_creates_missing_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"])
            state.unlink()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_CHECK_STATE_NOT_FOUND"):
                mod.evaluate(db, state, check_only=True)
            self.assertFalse(state.exists())

    def test_check_only_never_creates_missing_private_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            db, _ = self.fixture(temp, ["income_market_research"])
            nested = Path(temp) / "private" / "missing" / "evolution.json"
            self.assertFalse(nested.parent.exists())
            with self.assertRaisesRegex(
                RuntimeError, "MASTER_EVOLUTION_CHECK_PARENT_NOT_FOUND"
            ):
                mod.evaluate(db, nested, check_only=True)
            self.assertFalse(nested.parent.exists())
            self.assertFalse(nested.exists())

    def test_check_only_refuses_tampered_prior_completion_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET output_data='{}' WHERE id=1"
                )
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED"):
                mod.evaluate(db, state, check_only=True)
            self.assertEqual(state.read_bytes(), before)

    def test_activation_wrapper_preflights_policy_before_every_master_cycle(self):
        script = (SCRIPT.parent.parent / "deploy" / "activate_vps_master_agent.sh").read_text(
            encoding="utf-8"
        )
        start = script.index('cat > "$master/run-cycle.sh.tmp"')
        end = script.index("\nSH\n", start)
        wrapper = script[start:end]
        self.assertLess(wrapper.index('flock -n 9'), wrapper.index('--check-only'))
        self.assertLess(wrapper.index('--check-only'), wrapper.index('recover_stale_tasks'))
        self.assertLess(wrapper.index('recover_stale_tasks'), wrapper.index('autonomous_master_loop'))
        self.assertIn('steps=1', wrapper)
        self.assertIn('MASTER_EVOLUTION_PREFLIGHT_BLOCKED_NO_TASK_EXECUTION', wrapper)
        self.assertIn('exit 75', wrapper)
        self.assertIn('if (( proposed < approved_before ))', wrapper)
        self.assertIn('MASTER_EVOLUTION_PREVIOUS_MAX_STEPS', wrapper)

    def _run_cycle_wrapper_with_fake_runtime(self, mode, *, proposed="20", previous="20"):
        """Execute the generated wrapper in a disposable HOME with a fake Python.

        The wrapper exercises real bash branching, flock, timeout and argument
        wiring. Neither Django nor a production runtime is touched.
        """
        source = (SCRIPT.parent.parent / "deploy" / "activate_vps_master_agent.sh").read_text(
            encoding="utf-8"
        )
        script = source.split('cat > "$master/run-cycle.sh.tmp" <<\'SH\'\n', 1)[1].split(
            "\nSH\n", 1
        )[0]
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "factory-runtime"
            master = base / "operations" / "master-agent"
            master.mkdir(parents=True)
            app = base / "django-app"
            app.mkdir(parents=True)
            (app / "manage.py").write_text("# test-only placeholder\n")
            binary = base / ".venv" / "bin" / "python"
            binary.parent.mkdir(parents=True)
            binary.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "mode = os.environ['FAKE_POLICY_MODE']\n"
                "if args == ['-']:\n"
                "    if mode == 'db_fail': sys.exit(11)\n"
                "    print('/fake/private.sqlite3')\n"
                "elif '--check-only' in args:\n"
                "    if mode == 'evaluate_fail': sys.exit(12)\n"
                "    if mode == 'malformed': print('MASTER_EVOLUTION_MAX_STEPS=999')\n"
                "    else: print('MASTER_EVOLUTION_MAX_STEPS='+os.environ['FAKE_PROPOSED'])\n"
                "    print('MASTER_EVOLUTION_PREVIOUS_MAX_STEPS='+os.environ['FAKE_PREVIOUS'])\n"
                "    print('MASTER_EVOLUTION_CHECK_ONLY='+('false' if mode == 'non_readonly' else 'true'))\n"
                "elif args and args[0] == 'manage.py':\n"
                "    with Path(os.environ['FAKE_CALL_LOG']).open('a') as out:\n"
                "        out.write(' '.join(args)+'\\n')\n"
                "else:\n"
                "    sys.exit(13)\n",
                encoding="utf-8",
            )
            binary.chmod(0o700)
            wrapper = Path(temp) / "run-cycle.sh"
            wrapper.write_text(script + "\n", encoding="utf-8")
            record = Path(temp) / "calls.log"
            env = dict(os.environ, HOME=temp, FAKE_POLICY_MODE=mode,
                       FAKE_PROPOSED=proposed, FAKE_PREVIOUS=previous,
                       FAKE_CALL_LOG=str(record))
            proc = subprocess.run(
                ["bash", str(wrapper)], cwd=temp, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=10,
            )
            calls = record.read_text(encoding="utf-8") if record.exists() else ""
            return proc.returncode, proc.stdout + proc.stderr, calls

    def test_existing_prior_safety_flags_cannot_be_flipped(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            good = json.loads(state.read_text())
            # All eight fields are security assertions; none grants an
            # operator, spending, publication or parallel execution capability.
            for field, expected in mod.MASTER_POLICY_INVARIANTS.items():
                modified = dict(good)
                if isinstance(expected, bool):
                    modified[field] = not expected
                elif isinstance(expected, int):
                    modified[field] = expected + 1
                else:
                    modified[field] = "another-agent" if field == "agent_code" else "unbounded"
                state.write_text(json.dumps(modified), encoding="utf-8")
                before = state.read_bytes()
                with self.assertRaisesRegex(
                    RuntimeError, "MASTER_EVOLUTION_PREVIOUS_POLICY_INVARIANT_VIOLATION"
                ):
                    mod.evaluate(db, state, check_only=True)
                self.assertEqual(state.read_bytes(), before)
            state.write_text(json.dumps(good), encoding="utf-8")
            os.chmod(state, 0o600)
            mod.evaluate(db, state, check_only=True)

    def test_check_only_refuses_legacy_incomplete_state_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"])
            os.chmod(state, 0o600)
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_CHECK_BASELINE_INCOMPLETE"):
                mod.evaluate(db, state, check_only=True)
            self.assertEqual(state.read_bytes(), before)
            # Only the scheduled, explicitly state-writing evaluator migrates it.
            mod.evaluate(db, state)
            self.assertIn("completed_guard", json.loads(state.read_text()))
            mod.evaluate(db, state, check_only=True)

    def test_check_only_refuses_world_readable_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"])
            mod.evaluate(db, state)
            os.chmod(state, 0o644)
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_CHECK_STATE_NOT_PRIVATE"):
                mod.evaluate(db, state, check_only=True)
            self.assertEqual(state.read_bytes(), before)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o644)

    def test_check_only_rejects_shared_state_hardlink_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"])
            mod.evaluate(db, state)
            linked = Path(temp) / "shared-evolution.json"
            os.link(state, linked)
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_STATE_UNSAFE"):
                mod.evaluate(db, state, check_only=True)
            self.assertEqual(state.read_bytes(), before)
            self.assertEqual(linked.read_bytes(), before)

    def test_check_only_refuses_removed_guard_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            good = json.loads(state.read_text())
            for field in ("completed_guard", "pending_prior_ids", "last_completed_task_id",
                          "commercial_publication_enabled", "parallel_master_tasks"):
                modified = dict(good)
                modified.pop(field)
                state.write_text(json.dumps(modified), encoding="utf-8")
                os.chmod(state, 0o600)
                before = state.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_CHECK_BASELINE_INCOMPLETE"):
                    mod.evaluate(db, state, check_only=True)
                self.assertEqual(state.read_bytes(), before)

    def test_generated_wrapper_blocks_tasks_if_integrity_check_fails(self):
        code, output, calls = self._run_cycle_wrapper_with_fake_runtime("evaluate_fail")
        self.assertEqual(code, 75, output)
        self.assertIn("MASTER_EVOLUTION_PREFLIGHT_BLOCKED_NO_TASK_EXECUTION", output)
        self.assertEqual(calls, "")

    def test_generated_wrapper_blocks_tasks_if_database_configuration_fails(self):
        code, output, calls = self._run_cycle_wrapper_with_fake_runtime("db_fail")
        self.assertEqual(code, 75, output)
        self.assertIn("MASTER_EVOLUTION_DB_SETTINGS_FAILED", output)
        self.assertEqual(calls, "")

    def test_generated_wrapper_rejects_malformed_policy_result(self):
        code, output, calls = self._run_cycle_wrapper_with_fake_runtime("malformed")
        self.assertEqual(code, 75, output)
        self.assertIn("MASTER_EVOLUTION_PREFLIGHT_INVALID_RESULT", output)
        self.assertEqual(calls, "")

    def test_generated_wrapper_rejects_nonreadonly_policy_response(self):
        code, output, calls = self._run_cycle_wrapper_with_fake_runtime("non_readonly")
        self.assertEqual(code, 75, output)
        self.assertIn("MASTER_EVOLUTION_PREFLIGHT_BLOCKED_NO_TASK_EXECUTION", output)
        self.assertEqual(calls, "")

    def test_generated_wrapper_runs_only_after_valid_fresh_policy(self):
        code, output, calls = self._run_cycle_wrapper_with_fake_runtime(
            "valid", proposed="20", previous="20"
        )
        self.assertEqual(code, 0, output)
        self.assertIn("MASTER_EVOLUTION_FRESH_PREFLIGHT_STEPS=20", output)
        self.assertIn("recover_stale_tasks", calls)
        self.assertIn("autonomous_master_loop --max-steps 20", calls)
        self.assertLess(calls.index("recover_stale_tasks"), calls.index("autonomous_master_loop"))

    def test_generated_wrapper_never_expands_uncommitted_adaptive_budget(self):
        code, output, calls = self._run_cycle_wrapper_with_fake_runtime(
            "valid", proposed="20", previous="1"
        )
        self.assertEqual(code, 0, output)
        self.assertIn("MASTER_EVOLUTION_FRESH_PREFLIGHT_STEPS=1", output)
        self.assertIn("autonomous_master_loop --max-steps 1", calls)

    def test_generated_wrapper_immediately_reduces_regressed_budget(self):
        code, output, calls = self._run_cycle_wrapper_with_fake_runtime(
            "valid", proposed="1", previous="20"
        )
        self.assertEqual(code, 0, output)
        self.assertIn("MASTER_EVOLUTION_FRESH_PREFLIGHT_STEPS=1", output)
        self.assertIn("autonomous_master_loop --max-steps 1", calls)

    def test_bare_verified_flag_cannot_claim_internal_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET output_data=? WHERE id=1",
                    (json.dumps({"verified_effect": True}),),
                )
            before = state.read_bytes()
            with self.assertRaisesRegex(
                RuntimeError, "MASTER_EVOLUTION_INCOMPLETE_VERIFIED_EVIDENCE"
            ):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_verified_claim_requires_action_and_nonempty_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            for bad in (
                {"verified_effect": True, "evidence": {"kind": "test"}},
                {"verified_effect": True, "action_performed": " ", "evidence": {"kind": "test"}},
                {"verified_effect": True, "action_performed": "done", "evidence": {}},
                {"verified_effect": True, "action_performed": "done", "evidence": {"kind": ""}},
                {"verified_effect": True, "action_performed": "done", "evidence": []},
            ):
                with sqlite3.connect(db) as conn:
                    conn.execute(
                        "UPDATE core_agenttask SET output_data=? WHERE id=1",
                        (json.dumps(bad),),
                    )
                before = state.read_bytes()
                with self.assertRaisesRegex(
                    RuntimeError, "MASTER_EVOLUTION_INCOMPLETE_VERIFIED_EVIDENCE"
                ):
                    mod.evaluate(db, state)
                self.assertEqual(state.read_bytes(), before)

    def test_verified_claim_requires_nonempty_execution_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agenttask SET execution_id='' WHERE id=1")
            before = state.read_bytes()
            with self.assertRaisesRegex(
                RuntimeError, "MASTER_EVOLUTION_INCOMPLETE_VERIFIED_EVIDENCE"
            ):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_verified_claim_requires_positive_execution_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            for attempt in (0, -1, None):
                with sqlite3.connect(db) as conn:
                    conn.execute(
                        "UPDATE core_agenttask SET attempt_count=? WHERE id=1",
                        (attempt,),
                    )
                before = state.read_bytes()
                with self.assertRaisesRegex(
                    RuntimeError, "MASTER_EVOLUTION_INCOMPLETE_VERIFIED_EVIDENCE"
                ):
                    mod.evaluate(db, state)
                self.assertEqual(state.read_bytes(), before)

    def test_late_task_with_fake_verified_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'queued','income_profit_optimize','{}')"
                )
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_opportunity_score',?)",
                    (json.dumps(self.proof()),),
                )
            mod.evaluate(db, state)
            self.assertEqual(json.loads(state.read_text())["pending_prior_ids"], [2])
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE core_agenttask SET status='completed',output_data=? WHERE id=2",
                    (json.dumps({"verified_effect": True}),),
                )
            before = state.read_bytes()
            with self.assertRaisesRegex(
                RuntimeError, "MASTER_EVOLUTION_INCOMPLETE_VERIFIED_EVIDENCE"
            ):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_fully_evidenced_task_remains_creditable_only_once(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            first = json.loads(state.read_text())
            self.assertEqual(first["delta"]["verified_completed_tasks"], 1)
            mod.evaluate(db, state)
            second = json.loads(state.read_text())
            self.assertEqual(second["delta"]["verified_completed_tasks"], 0)

    def test_database_identity_survives_in_place_task_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            original = json.loads(state.read_text())["database_identity"]
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO core_agenttask(agent_id,status,action_type,output_data) "
                    "VALUES (1,'completed','income_profit_optimize',?)",
                    (json.dumps(self.proof()),),
                )
            mod.evaluate(db, state)
            result = json.loads(state.read_text())
            self.assertEqual(result["database_identity"], original)
            self.assertEqual(result["delta"]["verified_completed_tasks"], 1)

    def test_restored_identical_database_with_new_inode_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            before = state.read_bytes()
            replacement = Path(temp) / "restored.sqlite3"
            shutil.copyfile(db, replacement)
            os.replace(replacement, db)
            self.assertNotEqual(db.stat().st_ino, json.loads(before)["database_identity"]["inode"])
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_DATABASE_REPLACED"):
                mod.evaluate(db, state, check_only=True)
            self.assertEqual(state.read_bytes(), before)
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_DATABASE_REPLACED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_private_state_database_identity_cannot_be_forged_by_type(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            good = json.loads(state.read_text())
            for bad in (True, "123", -1):
                candidate = json.loads(json.dumps(good))
                candidate["database_identity"]["inode"] = bad
                state.write_text(json.dumps(candidate))
                before = state.read_bytes()
                with self.assertRaisesRegex(
                    RuntimeError, "MASTER_EVOLUTION_DATABASE_IDENTITY_INVALID"
                ):
                    mod.evaluate(db, state, check_only=True)
                self.assertEqual(state.read_bytes(), before)

    def test_agent_identity_change_in_same_database_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            before = state.read_bytes()
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE core_agent SET active=0 WHERE id=1")
                conn.execute(
                    "INSERT INTO core_agent(id,code,active) "
                    "VALUES (2,'economic-master-agent',1)"
                )
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_DATABASE_REPLACED"):
                mod.evaluate(db, state)
            self.assertEqual(state.read_bytes(), before)

    def test_check_only_requires_database_identity_in_saved_state(self):
        with tempfile.TemporaryDirectory() as temp:
            db, state = self.fixture(temp, ["income_market_research"], previous_steps=20)
            mod.evaluate(db, state)
            data = json.loads(state.read_text())
            data.pop("database_identity")
            state.write_text(json.dumps(data))
            before = state.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "MASTER_EVOLUTION_CHECK_BASELINE_INCOMPLETE"):
                mod.evaluate(db, state, check_only=True)
            self.assertEqual(state.read_bytes(), before)

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
