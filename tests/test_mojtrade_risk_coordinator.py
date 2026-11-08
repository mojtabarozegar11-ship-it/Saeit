"""Invariant tests for the DEMO-only central risk reservation ledger."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
import importlib.util
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
        self.ledger.settle(f"{1:032x}", "123", filled=True)
        self.ledger.reserve(self.admission(2))
        self.ledger.reserve(self.admission(3))
        with self.assertRaisesRegex(risk.Denied, "position_cap"):
            self.ledger.reserve(self.admission(4))

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
            "/v1/commit", {"account": "123", "request_id": f"{2:032x}"})
        self.assertEqual((status, body), (200, "SETTLED"))


if __name__ == "__main__":
    unittest.main()
