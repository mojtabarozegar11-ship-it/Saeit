"""Invariant tests for the DEMO-only central risk reservation ledger."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
import importlib.util
import json
import threading
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MODULE = Path(__file__).resolve().parents[1] / "trading" / "mojtrade_risk_coordinator.py"
spec = importlib.util.spec_from_file_location("mojtrade_risk_coordinator", MODULE)
risk = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = risk
spec.loader.exec_module(risk)

DAY = "2026-11-08"
TICK = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc).timestamp()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.now = TICK
        self.path = str(Path(self.dir.name) / "ledger.sqlite")
        self.ledger = risk.Ledger(self.path, enabled=True, clock=lambda: self.now)

    def tearDown(self):
        self.dir.cleanup()

    def seed(self, account="123"):
        self.ledger.seed_day(account, DAY, "1000.00")

    def admission(self, sequence, account="123", equity="1000",
                  realized="0", positions=0):
        return risk.Admission.parse({
            "mode": "demo",
            "account": account, "day": DAY, "request_id": f"{sequence:032x}",
            "equity": equity, "realized_today": realized,
            "open_positions": str(positions),
        }, DAY)

    def test_unenrolled_account_fails_closed(self):
        with self.assertRaisesRegex(risk.Denied, "baseline_not_enrolled"):
            self.ledger.reserve(self.admission(1))

    def test_disabled_controller_fails_closed(self):
        self.seed()
        self.ledger.enabled = False
        with self.assertRaisesRegex(risk.Denied, "disabled"):
            self.ledger.reserve(self.admission(1))

    def test_reservation_idempotency(self):
        self.seed()
        self.assertEqual(self.ledger.reserve(self.admission(1)), f"{1:032x}")
        with self.assertRaisesRegex(risk.Denied, "duplicate_request"):
            self.ledger.reserve(self.admission(1))

    def test_concurrent_reservations_never_exceed_three(self):
        self.seed()
        with ThreadPoolExecutor(max_workers=12) as executor:
            outcomes = list(executor.map(self.try_reserve, range(1, 15)))
        self.assertEqual(outcomes.count(True), 3)

    def try_reserve(self, i):
        try:
            self.ledger.reserve(self.admission(i))
            return True
        except risk.Denied:
            return False

    def test_count_includes_broker_positions(self):
        self.seed()
        self.ledger.reserve(self.admission(1, positions=2))
        with self.assertRaisesRegex(risk.Denied, "position_cap"):
            self.ledger.reserve(self.admission(2, positions=2))

    def test_cancel_frees_reservation(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.ledger.settle(f"{1:032x}", "123", filled=False)
        self.assertEqual(self.ledger.reserve(self.admission(2)), f"{2:032x}")

    def test_commit_retains_short_term_capacity(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")
        self.ledger.reserve(self.admission(2))
        self.ledger.reserve(self.admission(3))
        with self.assertRaisesRegex(risk.Denied, "position_cap"):
            self.ledger.reserve(self.admission(4))

    def test_commit_ack_replay_is_idempotent_and_does_not_extend_expiry(self):
        self.seed()
        request_id = f"{1:032x}"
        self.ledger.reserve(self.admission(1))
        self.ledger.settle(request_id, "123", filled=True, position_id="801")
        with self.ledger._readonly_connection() as db:
            before = db.execute(
                "SELECT state, expires, created FROM reservations WHERE request_id=?",
                (request_id,),
            ).fetchone()
        self.now += risk.TTL_SECONDS + 10
        self.ledger.settle(request_id, "123", filled=True, position_id="801")
        with self.ledger._readonly_connection() as db:
            after = db.execute(
                "SELECT state, expires, created FROM reservations WHERE request_id=?",
                (request_id,),
            ).fetchone()
        self.assertEqual(before, after)
        self.assertEqual(before[0], "committed")
        self.assertEqual(self.ledger.status("123", DAY)["active_reservations"], 0)

    def test_cancel_ack_replay_is_idempotent(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.ledger.settle(f"{1:032x}", "123", filled=False)
        self.ledger.settle(f"{1:032x}", "123", filled=False)
        self.assertEqual(self.ledger.status("123", DAY)["active_reservations"], 0)

    def test_opposite_settlement_is_never_accepted(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.ledger.reserve(self.admission(2))
        self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")
        self.ledger.settle(f"{2:032x}", "123", filled=False)
        with self.assertRaisesRegex(risk.Denied, "settlement_conflict"):
            self.ledger.settle(f"{1:032x}", "123", filled=False)
        with self.assertRaisesRegex(risk.Denied, "settlement_conflict"):
            self.ledger.settle(f"{2:032x}", "123", filled=True, position_id="802")

    def test_wrong_account_cannot_replay_settlement(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")
        with self.assertRaisesRegex(risk.Denied, "unknown_or_expired_reservation"):
            self.ledger.settle(f"{1:032x}", "456", filled=True, position_id="801")

    def test_expired_unsettled_request_cannot_be_committed_by_retry(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.now += risk.TTL_SECONDS + 1
        with self.assertRaisesRegex(risk.Denied, "unknown_or_expired_reservation"):
            self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")

    def test_success_requires_realistic_broker_position_id(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        for position_id in ("", "0", "-1", "1.0", "nan", "x", "1" * 21):
            with self.subTest(position_id=position_id):
                with self.assertRaisesRegex(risk.Denied, "missing_broker_position_id"):
                    self.ledger.settle(f"{1:032x}", "123", filled=True,
                                       position_id=position_id)
        self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")

    def test_cancellation_rejects_broker_position_id(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        with self.assertRaisesRegex(risk.Denied, "unexpected_broker_position_id"):
            self.ledger.settle(f"{1:032x}", "123", filled=False, position_id="801")
        self.ledger.settle(f"{1:032x}", "123", filled=False)

    def test_duplicate_ack_cannot_replace_original_broker_position(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")
        with self.assertRaisesRegex(risk.Denied, "settlement_conflict"):
            self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="802")
        rows = self.ledger.receipts("123", DAY)["receipts"]
        self.assertEqual(rows[0]["reported_broker_position_id"], "801")

    def test_two_requests_cannot_claim_same_broker_position(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.ledger.reserve(self.admission(2))
        self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")
        with self.assertRaisesRegex(risk.Denied, "broker_position_reuse"):
            self.ledger.settle(f"{2:032x}", "123", filled=True, position_id="801")
        self.ledger.settle(f"{2:032x}", "123", filled=True, position_id="802")

    def test_readonly_receipt_report_is_not_broker_verification(self):
        self.seed()
        for n in (1, 2, 3):
            self.ledger.reserve(self.admission(n))
        self.ledger.settle(f"{1:032x}", "123", filled=True, position_id="801")
        self.ledger.settle(f"{2:032x}", "123", filled=False)
        report = self.ledger.receipts("123", DAY)
        self.assertFalse(report["broker_verified"])
        self.assertFalse(report["truncated"])
        self.assertEqual(len(report["receipts"]), 3)
        by_request = {r["request_id"]: r for r in report["receipts"]}
        self.assertEqual(by_request[f"{1:032x}"]["state"], "committed")
        self.assertEqual(by_request[f"{1:032x}"]["reported_broker_position_id"], "801")
        self.assertIsNone(by_request[f"{2:032x}"]["reported_broker_position_id"])
        self.assertEqual(by_request[f"{3:032x}"]["state"], "reserved")
        with self.ledger._readonly_connection() as db:
            self.assertEqual(db.execute("PRAGMA query_only").fetchone()[0], 1)

    def test_receipt_report_rejects_bad_scope(self):
        with self.assertRaisesRegex(risk.Denied, "invalid_identity"):
            self.ledger.receipts("abc", DAY)
        with self.assertRaisesRegex(risk.Denied, "invalid_day"):
            self.ledger.receipts("123", "invalid")

    def test_receipt_report_is_bounded_and_explicitly_truncated(self):
        self.seed()
        with self.ledger._connection() as db:
            for n in range(101):
                db.execute(
                    "INSERT INTO reservations(request_id,account,day,state,expires,created) "
                    "VALUES (?,?,?,'cancelled',?,?)",
                    (f"{n:032x}", "123", DAY, self.now + 10, self.now + n),
                )
        report = self.ledger.receipts("123", DAY)
        self.assertTrue(report["truncated"])
        self.assertEqual(len(report["receipts"]), 100)

    def test_existing_ledger_is_migrated_without_losing_old_receipts(self):
        old_path = str(Path(self.dir.name) / "old.sqlite")
        with risk.sqlite3.connect(old_path) as db:
            db.execute("CREATE TABLE reservations (request_id TEXT PRIMARY KEY, "
                       "account TEXT NOT NULL,day TEXT NOT NULL,state TEXT NOT NULL, "
                       "expires REAL NOT NULL,created REAL NOT NULL)")
            db.execute("INSERT INTO reservations VALUES (?,?,?,'cancelled',?,?)",
                       (f"{7:032x}", "123", DAY, self.now + 10, self.now))
        migrated = risk.Ledger(old_path, enabled=True, clock=lambda: self.now)
        report = migrated.receipts("123", DAY)
        self.assertEqual(len(report["receipts"]), 1)
        self.assertEqual(report["receipts"][0]["request_id"], f"{7:032x}")
        self.assertIsNone(report["receipts"][0]["reported_broker_position_id"])

    def test_expiry_does_not_allow_request_replay(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.now += risk.TTL_SECONDS + 1
        self.ledger.reserve(self.admission(2))
        with self.assertRaisesRegex(risk.Denied, "duplicate_request"):
            self.ledger.reserve(self.admission(1))

    def test_daily_equity_stop_latched_after_recovery(self):
        self.seed()
        with self.assertRaisesRegex(risk.Denied, "daily_loss_reached"):
            self.ledger.reserve(self.admission(1, equity="979"))
        with self.assertRaisesRegex(risk.Denied, "risk_halted"):
            self.ledger.reserve(self.admission(2, equity="1010"))

    def test_realized_loss_stop_also_latched(self):
        self.seed()
        with self.assertRaisesRegex(risk.Denied, "daily_loss_reached"):
            self.ledger.reserve(self.admission(1, realized="-21"))
        with self.assertRaisesRegex(risk.Denied, "risk_halted"):
            self.ledger.reserve(self.admission(2))

    def test_state_is_persistent_across_restart(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        restarted = risk.Ledger(self.path, enabled=True, clock=lambda: self.now)
        with self.assertRaisesRegex(risk.Denied, "duplicate_request"):
            restarted.reserve(self.admission(1))
        with self.assertRaisesRegex(risk.Denied, "position_cap"):
            restarted.reserve(self.admission(2, positions=2))

    def test_seed_cannot_reset_day_baseline(self):
        self.seed()
        with self.assertRaises(Exception):
            self.ledger.seed_day("123", DAY, "980")

    def test_other_account_is_separate(self):
        self.seed()
        self.seed("456")
        for n in (1, 2, 3):
            self.ledger.reserve(self.admission(n))
        self.assertEqual(self.ledger.reserve(self.admission(4, account="456")), f"{4:032x}")

    def test_invalid_nonfinite_data_rejected(self):
        for value in ("nan", "Infinity", "-Infinity", "0"):
            with self.subTest(equity=value), self.assertRaises(risk.Denied):
                self.admission(1, equity=value)

    def test_day_replay_rejected(self):
        with self.assertRaisesRegex(risk.Denied, "stale_day"):
            risk.Admission.parse({
                "mode": "demo",
                "account": "123", "day": "2026-11-07",
                "request_id": f"{1:032x}", "equity": "1000",
                "realized_today": "0", "open_positions": "0",
            }, DAY)

    def test_near_midnight_rollover_uses_persisted_prior_equity(self):
        prior = "2026-11-08"
        next_day = "2026-11-09"
        midnight = datetime(2026, 11, 9, tzinfo=timezone.utc).timestamp()
        self.now = midnight - 30
        self.seed()
        self.ledger.reserve(self.admission(1, equity="995"))
        self.now = midnight + 10
        next_request = risk.Admission.parse({
            "mode": "demo", "account": "123", "day": next_day,
            "request_id": f"{2:032x}", "equity": "995", "realized_today": "0",
            "open_positions": "0",
        }, next_day)
        self.assertEqual(self.ledger.reserve(next_request), f"{2:032x}")
        with self.ledger._connection() as db:
            state = db.execute(
                "SELECT baseline FROM day_state WHERE account=? AND day=?",
                ("123", next_day),
            ).fetchone()
        self.assertEqual(state[0], "995")

    def test_stale_midnight_snapshot_blocks_rollover(self):
        self.seed()
        midnight = datetime(2026, 11, 9, tzinfo=timezone.utc).timestamp()
        self.now = midnight + 10
        future = risk.Admission.parse({
            "mode": "demo", "account": "123", "day": "2026-11-09",
            "request_id": f"{2:032x}", "equity": "1000", "realized_today": "0",
            "open_positions": "0",
        }, "2026-11-09")
        with self.assertRaisesRegex(risk.Denied, "baseline_not_enrolled"):
            self.ledger.reserve(future)

    def test_observe_updates_equity_without_reservations_when_positions_full(self):
        self.seed()
        self.ledger.observe(self.admission(1, equity="995", positions=3))
        with self.ledger._connection() as db:
            equity = db.execute(
                "SELECT last_equity FROM day_state WHERE account=? AND day=?",
                ("123", DAY),
            ).fetchone()[0]
            reserved = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(equity, "995")
        self.assertEqual(reserved, 0)

    def test_observe_latches_equity_stop_across_restart(self):
        self.seed()
        with self.assertRaisesRegex(risk.Denied, "daily_loss_reached"):
            self.ledger.observe(self.admission(1, equity="979", positions=3))
        restarted = risk.Ledger(self.path, enabled=True, clock=lambda: self.now)
        with self.assertRaisesRegex(risk.Denied, "risk_halted"):
            restarted.reserve(self.admission(2, equity="1000"))

    def test_observe_latches_realized_stop_without_order_attempt(self):
        self.seed()
        with self.assertRaisesRegex(risk.Denied, "daily_loss_reached"):
            self.ledger.observe(self.admission(1, realized="-21"))
        with self.assertRaisesRegex(risk.Denied, "risk_halted"):
            self.ledger.observe(self.admission(2, realized="0"))

    def test_observe_rolls_baseline_without_new_order(self):
        self.seed()
        midnight = datetime(2026, 11, 9, tzinfo=timezone.utc).timestamp()
        self.now = midnight - 30
        self.ledger.observe(self.admission(1, equity="991", positions=3))
        self.now = midnight + 10
        next_day = "2026-11-09"
        observed = risk.Admission.parse({
            "mode": "demo", "account": "123", "day": next_day,
            "request_id": f"{2:032x}", "equity": "991",
            "realized_today": "0", "open_positions": "3",
        }, next_day)
        self.ledger.observe(observed)
        with self.ledger._connection() as db:
            state = db.execute(
                "SELECT baseline FROM day_state WHERE account=? AND day=?",
                ("123", next_day),
            ).fetchone()[0]
        self.assertEqual(state, "991")

    def test_observation_allowed_while_reservations_disabled(self):
        self.seed()
        self.ledger.enabled = False
        self.ledger.observe(self.admission(1))
        with self.assertRaisesRegex(risk.Denied, "disabled"):
            self.ledger.reserve(self.admission(2))

    def test_direct_observation_rejects_stale_day(self):
        self.seed()
        invalid = risk.Admission("123", "2026-11-07", f"{1:032x}",
                                 risk.Decimal("1000"), risk.Decimal("0"), 0)
        with self.assertRaisesRegex(risk.Denied, "stale_day"):
            self.ledger.observe(invalid)

    def test_operator_status_is_read_only_and_reports_risk_state(self):
        self.seed()
        self.ledger.observe(self.admission(1, equity="995"))
        before = self.ledger.status("123", DAY)
        self.assertEqual(before["baseline"], "1000.00")
        self.assertEqual(before["last_equity"], "995")
        self.assertFalse(before["halted"])
        self.assertEqual(before["active_reservations"], 0)
        self.assertTrue(before["telemetry_fresh"])
        self.assertTrue(before["demo_reservations_enabled"])
        with self.ledger._connection() as db:
            updated_before = db.execute(
                "SELECT updated FROM day_state WHERE account=? AND day=?",
                ("123", DAY),
            ).fetchone()[0]
        self.now += 125
        after = self.ledger.status("123", DAY)
        self.assertFalse(after["telemetry_fresh"])
        self.assertEqual(after["last_risk_update_age_seconds"], 125)
        with self.ledger._connection() as db:
            updated_after = db.execute(
                "SELECT updated FROM day_state WHERE account=? AND day=?",
                ("123", DAY),
            ).fetchone()[0]
        self.assertEqual(updated_before, updated_after)

    def test_status_reports_latched_stop_and_expiring_reservations(self):
        self.seed()
        self.ledger.reserve(self.admission(1))
        self.assertEqual(self.ledger.status("123", DAY)["active_reservations"], 1)
        with self.assertRaisesRegex(risk.Denied, "daily_loss_reached"):
            self.ledger.observe(self.admission(2, equity="979"))
        self.assertTrue(self.ledger.status("123", DAY)["halted"])
        self.now += risk.TTL_SECONDS + 1
        self.assertEqual(self.ledger.status("123", DAY)["active_reservations"], 0)

    def test_status_denies_unenrolled_or_invalid_identity(self):
        with self.assertRaisesRegex(risk.Denied, "baseline_not_enrolled"):
            self.ledger.status("123", DAY)
        with self.assertRaisesRegex(risk.Denied, "invalid_identity"):
            self.ledger.status("123;DROP", DAY)
        with self.assertRaisesRegex(risk.Denied, "invalid_day"):
            self.ledger.status("123", "2026-99-99")

    def test_status_sqlite_connection_is_truly_read_only(self):
        self.seed()
        with self.ledger._readonly_connection() as db:
            self.assertEqual(db.execute("PRAGMA query_only").fetchone()[0], 1)
            with self.assertRaises(risk.sqlite3.OperationalError):
                db.execute("UPDATE day_state SET halted=1 WHERE account='123'")
        self.assertFalse(self.ledger.status("123", DAY)["halted"])

    def test_status_does_not_recreate_missing_database(self):
        fresh_path = Path(self.dir.name) / "lost.sqlite"
        separate = risk.Ledger(str(fresh_path), enabled=False, clock=lambda: self.now)
        fresh_path.unlink()
        with self.assertRaises(risk.sqlite3.OperationalError):
            separate.status("123", DAY)
        self.assertFalse(fresh_path.exists())


class HttpProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        ledger = risk.Ledger(
            str(Path(self.tempdir.name) / "http.sqlite"), enabled=True, clock=lambda: TICK)
        ledger.seed_day("123", DAY, "1000")
        class IsolatedHandler(risk.Handler):
            pass
        IsolatedHandler.ledger = ledger
        IsolatedHandler.token = "a" * 40
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), IsolatedHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tempdir.cleanup()

    def post(self, path, fields, token="a" * 40):
        request = Request(
            self.base + path, data=urlencode(fields).encode("ascii"),
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            return response.status, response.read().decode("ascii")

    def test_unauthorized_request_never_reserves(self):
        data = dict(mode="demo", account="123", day=DAY, request_id=f"{1:032x}",
                    equity="1000", realized_today="0", open_positions="0")
        with self.assertRaises(HTTPError) as caught:
            self.post("/v1/reserve", data, token="wrong")
        self.assertEqual(caught.exception.code, 401)
        self.assertEqual(self.post("/v1/reserve", data)[1], "GRANTED|" + f"{1:032x}")

    def test_reservation_and_settlement_http(self):
        data = dict(mode="demo", account="123", day=DAY, request_id=f"{2:032x}",
                    equity="1000", realized_today="0", open_positions="0")
        status, body = self.post("/v1/reserve", data)
        self.assertEqual((status, body), (200, "GRANTED|" + f"{2:032x}"))
        status, body = self.post(
            "/v1/commit", {"account": "123", "request_id": f"{2:032x}",
                            "broker_position_id": "802"})
        self.assertEqual((status, body), (200, "SETTLED"))

    def test_lost_ack_retry_returns_settled_over_http(self):
        data = dict(mode="demo", account="123", day=DAY, request_id=f"{5:032x}",
                    equity="1000", realized_today="0", open_positions="0")
        self.post("/v1/reserve", data)
        body = {"account": "123", "request_id": f"{5:032x}",
                "broker_position_id": "805"}
        self.assertEqual(self.post("/v1/commit", body), (200, "SETTLED"))
        self.assertEqual(self.post("/v1/commit", body), (200, "SETTLED"))
        with self.assertRaises(HTTPError) as caught:
            self.post("/v1/cancel", {"account": "123", "request_id": f"{5:032x}"})
        self.assertEqual(caught.exception.code, 409)

    def test_http_receipt_report_requires_authentication_and_exposes_unverified_status(self):
        data = dict(mode="demo", account="123", day=DAY, request_id=f"{6:032x}",
                    equity="1000", realized_today="0", open_positions="0")
        self.post("/v1/reserve", data)
        self.post("/v1/commit", {"account": "123", "request_id": f"{6:032x}",
                                 "broker_position_id": "806"})
        endpoint = self.base + "/v1/receipts?account=123&day=" + DAY
        with self.assertRaises(HTTPError) as caught:
            urlopen(endpoint, timeout=2)
        self.assertEqual(caught.exception.code, 401)
        req = Request(endpoint, headers={"Authorization": "Bearer " + "a" * 40})
        with urlopen(req, timeout=2) as response:
            report = json.loads(response.read().decode("ascii"))
        self.assertFalse(report["broker_verified"])
        self.assertEqual(report["receipts"][0]["reported_broker_position_id"], "806")

    def test_http_commit_without_broker_reference_fails_closed(self):
        data = dict(mode="demo", account="123", day=DAY, request_id=f"{7:032x}",
                    equity="1000", realized_today="0", open_positions="0")
        self.post("/v1/reserve", data)
        with self.assertRaises(HTTPError) as caught:
            self.post("/v1/commit", {"account": "123", "request_id": f"{7:032x}"})
        self.assertEqual(caught.exception.code, 409)

    def test_authenticated_observation_http_does_not_reserve(self):
        data = dict(mode="demo", account="123", day=DAY, request_id=f"{3:032x}",
                    equity="999", realized_today="0", open_positions="3")
        self.assertEqual(self.post("/v1/observe", data), (200, "OBSERVED"))
        with self.server.RequestHandlerClass.ledger._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 0)

    def test_observation_http_unauthorized_is_denied(self):
        data = dict(mode="demo", account="123", day=DAY, request_id=f"{4:032x}",
                    equity="999", realized_today="0", open_positions="0")
        with self.assertRaises(HTTPError) as caught:
            self.post("/v1/observe", data, token="wrong")
        self.assertEqual(caught.exception.code, 401)

    def test_status_http_requires_token_and_does_not_mutate(self):
        url = self.base + "/v1/status?account=123&day=" + DAY
        with self.assertRaises(HTTPError) as caught:
            urlopen(url, timeout=2)
        self.assertEqual(caught.exception.code, 401)
        request = Request(url, headers={"Authorization": "Bearer " + "a" * 40})
        with urlopen(request, timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("application/json", response.headers["Content-Type"])
            snapshot = json.loads(response.read().decode("ascii"))
        self.assertEqual(snapshot["account"], "123")
        self.assertEqual(snapshot["baseline"], "1000")
        self.assertFalse(snapshot["halted"])
        with self.server.RequestHandlerClass.ledger._connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 0)

    def test_status_http_rejects_duplicate_and_unexpected_query(self):
        for suffix in ("account=123&account=456&day=" + DAY,
                       "account=123&day=" + DAY + "&secret=1"):
            request = Request(
                self.base + "/v1/status?" + suffix,
                headers={"Authorization": "Bearer " + "a" * 40},
            )
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=2)
            self.assertEqual(caught.exception.code, 409)


if __name__ == "__main__":
    unittest.main()
