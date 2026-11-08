"""Offline, zero-order, no-GitHub runtime supervision regression tests."""

import copy
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "scripts" / "mojtrade_offline_supervisor.py"
if not SRC.is_file():
    SRC = HERE / "mojtrade_offline_supervisor.py"
sys.path.insert(0, str(SRC.parent))
sys.path.insert(0, str(HERE))
import test_mojtrade_independent_validation as prior

spec = importlib.util.spec_from_file_location("mojtrade_offline_supervisor", SRC)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class OfflineSupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = prior.fixture.market_data()
        cls.report = prior.oos.foundry.invent(cls.train, seed=173, max_trials=64, cost_bps=2.0)
        cls.unseen = prior.unseen_period(cls.train)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.frozen_dir = self.root / "frozen"
        self.frozen_dir.mkdir(mode=0o700)
        self.ledger = self.frozen_dir / "oos.jsonl"
        prior.oos.validate_once(self.report, self.train, self.unseen, self.ledger)
        paths = {}
        for key, data in (("foundry_report", self.report),
                          ("training_data", self.train), ("unseen_data", self.unseen)):
            path = self.root / (key + ".json")
            path.write_text(json.dumps(data), encoding="utf-8")
            os.chmod(path, 0o600)
            paths[key] = str(path)
        self.config = self.root / "config.json"
        paths.update({"schema": supervisor.SCHEMA, "private_oos_ledger": str(self.ledger)})
        self.config.write_text(json.dumps(paths), encoding="utf-8")
        os.chmod(self.config, 0o600)

    def tearDown(self):
        self.temp.cleanup()

    def test_provenance_is_unverified_even_when_frozen_evidence_exists(self):
        output = supervisor.inspect(self.config, self.state)
        self.assertEqual(output["state"], "RESEARCH_EVIDENCE_OBSERVED_UNVERIFIED")
        self.assertEqual(output["real_orders"], 0)
        self.assertEqual(output["public_signals"], 0)
        self.assertFalse(output["broker_eligible"])
        self.assertFalse(output["publish_eligible"])
        self.assertFalse(output["commercial_ready"])
        self.assertFalse(output["git_hub_runtime_dependency"])
        self.assertIn("source_and_observation_time_not_authenticated", output["blockers"])

    def test_only_unique_material_transitions_are_recorded(self):
        first = supervisor.inspect_and_record(self.config, self.state)
        second = supervisor.inspect_and_record(self.config, self.state)
        self.assertTrue(first["new_material_transition"])
        self.assertFalse(second["new_material_transition"])
        self.assertEqual(first["journal_sequence"], 1)
        self.assertEqual(second["journal_sequence"], 1)
        self.assertEqual(len((self.state / "state-changes.jsonl").read_text().splitlines()), 1)
        self.assertTrue((self.state / "health.json").is_file())
        self.assertEqual(stat.S_IMODE((self.state / "health.json").stat().st_mode), 0o600)

    def test_health_age_separately_detects_staleness(self):
        supervisor.inspect_and_record(self.config, self.state)
        status_file = self.state / "health.json"
        source = json.loads(status_file.read_text())
        recorded = datetime.fromisoformat(source["checked_at_utc"])
        fresh = supervisor.read_health(self.state, now=recorded + timedelta(seconds=50))
        stale = supervisor.read_health(self.state, now=recorded + timedelta(seconds=181))
        self.assertEqual(fresh["health_state"], "RECENT_HEARTBEAT_NOT_PROOF_RUNNING")
        self.assertEqual(stale["health_state"], "STALE_HEARTBEAT")
        self.assertFalse(fresh["commercial_ready"])
        self.assertFalse(stale["broker_eligible"])

    def test_missing_or_corrupt_health_is_never_healthy(self):
        self.assertEqual(supervisor.read_health(self.state)["health_state"],
                         "MISSING_OR_CORRUPT_HEARTBEAT")
        supervisor.inspect_and_record(self.config, self.state)
        heartbeat = self.state / "health.json"
        raw = json.loads(heartbeat.read_text())
        raw["commercial_ready"] = True
        heartbeat.write_text(json.dumps(raw))
        self.assertEqual(supervisor.read_health(self.state)["health_state"],
                         "MISSING_OR_CORRUPT_HEARTBEAT")

    def test_future_heartbeat_is_clock_skew_blocked(self):
        supervisor.inspect_and_record(self.config, self.state)
        checked = datetime.fromisoformat(json.loads(
            (self.state / "health.json").read_text())["checked_at_utc"])
        result = supervisor.read_health(self.state, now=checked - timedelta(seconds=15))
        self.assertEqual(result["health_state"], "CLOCK_SKEW_BLOCKED")

    def test_second_supervisor_cannot_acquire_process_lock(self):
        with supervisor._single_instance(self.state):
            with self.assertRaisesRegex(supervisor.SupervisorReject,
                                        "another_supervisor_already_active"):
                with supervisor._single_instance(self.state):
                    self.fail("a second active supervisor was permitted")
        with supervisor._single_instance(self.state):
            pass

    def test_symlinked_process_lock_and_heartbeat_rejected(self):
        (self.state / "supervisor.lock").symlink_to(self.root / "missing-lock")
        with self.assertRaisesRegex(supervisor.SupervisorReject, "unsafe_supervisor_lock_symlink"):
            with supervisor._single_instance(self.state):
                pass
        (self.state / "supervisor.lock").unlink()
        (self.state / "health.json").symlink_to(self.root / "missing-health")
        with self.assertRaisesRegex(supervisor.SupervisorReject, "unsafe_heartbeat_symlink"):
            supervisor.inspect_and_record(self.config, self.state)

    def test_read_only_status_cli_needs_no_config_or_network(self):
        supervisor.inspect_and_record(self.config, self.state)
        before = (self.state / "state-changes.jsonl").read_text()
        stream = io.StringIO()
        with patch("socket.socket", side_effect=AssertionError("unexpected network")):
            with redirect_stdout(stream):
                self.assertEqual(supervisor.main(["--status", "--state-dir",
                                                  str(self.state)]), 0)
        status = json.loads(stream.getvalue())
        self.assertEqual(status["health_state"], "RECENT_HEARTBEAT_NOT_PROOF_RUNNING")
        self.assertEqual(before, (self.state / "state-changes.jsonl").read_text())

    def test_stop_and_resume_are_two_distinct_transitions(self):
        supervisor.inspect_and_record(self.config, self.state)
        stop = self.state / "STOP"
        stop.touch()
        paused = supervisor.inspect_and_record(self.config, self.state)
        self.assertEqual(paused["state"], "OPERATOR_STOPPED")
        self.assertEqual(paused["journal_sequence"], 2)
        stop.unlink()
        resumed = supervisor.inspect_and_record(self.config, self.state)
        self.assertEqual(resumed["state"], "RESEARCH_EVIDENCE_OBSERVED_UNVERIFIED")
        self.assertEqual(resumed["journal_sequence"], 3)

    def test_unfrozen_or_missing_holdout_is_blocked(self):
        self.ledger.unlink()
        observed = supervisor.inspect(self.config, self.state)
        self.assertEqual(observed["state"], "BLOCKED_EVIDENCE")
        self.assertIsNone(observed["evidence_receipt_sha256"])

    def test_tampered_ledger_is_blocked_without_replacement(self):
        raw = self.ledger.read_text()
        altered = json.loads(raw)
        altered["receipt"]["broker_eligible"] = True
        self.ledger.write_text(json.dumps(altered) + "\n")
        blocked = supervisor.inspect(self.config, self.state)
        self.assertEqual(blocked["state"], "BLOCKED_EVIDENCE")
        self.assertIn("frozen_journal_integrity_invalid", " ".join(blocked["blockers"]))
        self.assertTrue(self.ledger.read_text().find('"broker_eligible": true') > 0)

    def test_modified_source_is_detected_as_blocked(self):
        raw = json.loads(self.config.read_text())
        data = json.loads(Path(raw["training_data"]).read_text())
        data["bars"][120]["close"] += 0.03
        Path(raw["training_data"]).write_text(json.dumps(data))
        event = supervisor.inspect(self.config, self.state)
        self.assertEqual(event["state"], "BLOCKED_EVIDENCE")

    def test_public_state_directory_rejected(self):
        os.chmod(self.state, 0o755)
        with self.assertRaisesRegex(supervisor.SupervisorReject, "private_0700"):
            supervisor.inspect(self.config, self.state)

    def test_nonprivate_config_is_blocked(self):
        os.chmod(self.config, 0o644)
        event = supervisor.inspect(self.config, self.state)
        self.assertEqual(event["state"], "BLOCKED_EVIDENCE")

    def test_symlink_stop_flag_fails_closed(self):
        (self.state / "STOP").symlink_to(self.root / "not-present")
        self.assertEqual(supervisor.inspect(self.config, self.state)["state"],
                         "OPERATOR_STOPPED")

    def test_corrupted_event_journal_rejected_without_overwriting(self):
        supervisor.inspect_and_record(self.config, self.state)
        target = self.state / "state-changes.jsonl"
        tampered = target.read_text().replace('"broker_eligible":false',
                                               '"broker_eligible":true')
        target.write_text(tampered)
        with self.assertRaisesRegex(supervisor.SupervisorReject, "journal_hash_chain_invalid"):
            supervisor.inspect_and_record(self.config, self.state)

    def test_duplicate_concurrent_events_do_not_multiply_reports(self):
        event = {"schema": supervisor.SCHEMA, "state": "BLOCKED_EVIDENCE", "real_orders": 0}
        with ThreadPoolExecutor(max_workers=4) as pool:
            result = list(pool.map(lambda _: supervisor.record_if_changed(event, self.state),
                                   range(8)))
        self.assertEqual(sum(x["transition_written"] for x in result), 1)
        self.assertEqual(len((self.state / "state-changes.jsonl").read_text().splitlines()), 1)

    def test_cli_one_shot_is_zero_order_and_does_not_use_network(self):
        stream = io.StringIO()
        with patch("socket.socket", side_effect=AssertionError("network used")):
            with redirect_stdout(stream):
                self.assertEqual(supervisor.main(["--config", str(self.config),
                                                  "--state-dir", str(self.state)]), 0)
        obj = json.loads(stream.getvalue())
        self.assertEqual(obj["real_orders"], 0)
        self.assertEqual(obj["public_signals"], 0)
        self.assertFalse(obj["commercial_ready"])

    def test_watch_mode_quits_immediately_on_local_stop(self):
        (self.state / "STOP").touch()
        stream = io.StringIO()
        with patch.object(supervisor.time, "sleep", side_effect=AssertionError("slept after stop")):
            with redirect_stdout(stream):
                self.assertEqual(supervisor.main(["--config", str(self.config),
                                                  "--state-dir", str(self.state),
                                                  "--watch"]), 0)
        self.assertEqual(json.loads(stream.getvalue())["state"], "OPERATOR_STOPPED")


if __name__ == "__main__":
    unittest.main()
