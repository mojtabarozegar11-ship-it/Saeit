"""Research-only portfolio risk gate; synthetic assertions, no broker calls."""

import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_portfolio_risk_gate.py"
SOURCE = REPO if REPO.is_file() else Path(__file__).with_name("mojtrade_portfolio_risk_gate.py")
spec = importlib.util.spec_from_file_location("mojtrade_portfolio_risk_gate", SOURCE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
NOW = datetime(2026, 11, 7, 18, tzinfo=timezone.utc)


def leg(ident="r1", symbol="EURUSD", strategy="strategy-A", *, qty="1000"):
    entry, stop = ("1.1000", "1.0950") if symbol == "EURUSD" else ("100", "99.5")
    return {"request_id": ident, "symbol": symbol, "strategy_id": strategy,
            "side": "BUY", "quantity": qty, "entry": entry,
            "stop": stop, "unit_value_cash_per_price_point": "1",
            "execution_buffer_cash": "1" if symbol == "EURUSD" else "2"}


def snapshot(proposals=None, **changes):
    result = {"account_id": "paper-a", "account_mode": "DEMO",
              "risk_day": NOW.date().isoformat(),
              "snapshot_at": NOW.isoformat(),
              "quote_at": (NOW - timedelta(seconds=1)).isoformat(),
              "equity_cash": "10000", "day_start_equity_cash": "10000",
              "peak_equity_cash": "10000", "consecutive_losses": 0,
              "open_positions": [], "proposals": proposals or [leg()]}
    result.update(changes)
    return result


class PortfolioRiskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.private = Path(self.temp.name) / "risk"
        self.private.mkdir(mode=0o700)
        self.db = self.private / "risk.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def reserve(self, payload):
        return gate.reserve_research_slots(payload, self.db, now=NOW)

    def test_one_safe_research_slot_has_zero_orders_and_no_broker_eligibility(self):
        report = self.reserve(snapshot())
        self.assertEqual(report["orders"], 0)
        self.assertEqual(report["execution"], "disabled")
        self.assertEqual(report["decisions"][0]["status"], "RESEARCH_SLOT_RESERVED")
        self.assertFalse(report["decisions"][0]["broker_eligible"])
        self.assertEqual(report["report_sha256"], gate._digest(
            {k: v for k, v in report.items() if k != "report_sha256"}))
        self.assertEqual(os.stat(self.db).st_mode & 0o777, 0o600)

    def test_identical_request_is_idempotent_and_payload_reuse_fails_closed(self):
        first = self.reserve(snapshot())
        self.assertEqual(first["decisions"], self.reserve(snapshot())["decisions"])
        changed = snapshot([leg(qty="2000")])
        with self.assertRaisesRegex(gate.RiskReject, "request_id_reused"):
            self.reserve(changed)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1)

    def test_batch_atomically_counts_each_approved_slot_before_next(self):
        proposals = [leg(f"r{i}", strategy=f"s{i}", qty="4000") for i in range(4)]
        result = self.reserve(snapshot(proposals))
        self.assertEqual([d["status"] for d in result["decisions"]],
                         ["RESEARCH_SLOT_RESERVED", "RESEARCH_SLOT_RESERVED",
                          "REJECTED", "REJECTED"])
        self.assertIn("symbol_concentration_budget", result["decisions"][2]["reasons"])

    def test_concurrent_requests_share_one_sqlite_risk_budget(self):
        self.reserve(snapshot([leg("initial", strategy="initial", qty="1000")]))
        def act(i):
            return self.reserve(snapshot([leg(f"req{i}", strategy=f"s{i}", qty="4000")]))
        with ThreadPoolExecutor(max_workers=6) as executor:
            receipts = list(executor.map(act, range(6)))
        allowed = sum(x["decisions"][0]["status"] == "RESEARCH_SLOT_RESERVED" for x in receipts)
        # Initial risk = 6; 4000 units risk=21 each; at most two fit symbol cap 50.
        self.assertEqual(allowed, 2)
        self.assertTrue(all(x["orders"] == 0 for x in receipts))

    def test_existing_open_positions_consume_shared_symbol_budget(self):
        first = leg("position-A", strategy="older-A", qty="4000")
        second = leg("position-B", strategy="older-B", qty="4000")
        for source in (first, second):
            source["position_id"] = source.pop("request_id")
        result = self.reserve(snapshot([leg("new", strategy="new-C", qty="4000")],
                                       open_positions=[first, second]))
        self.assertEqual(result["decisions"][0]["status"], "REJECTED")
        self.assertIn("symbol_concentration_budget", result["decisions"][0]["reasons"])

    def test_broker_live_mode_always_rejected_before_database_creation(self):
        with self.assertRaisesRegex(gate.RiskReject, "live_account"):
            self.reserve(snapshot(account_mode="LIVE"))
        self.assertFalse(self.db.exists())

    def test_stale_quote_and_future_snapshot_fail_closed(self):
        with self.assertRaisesRegex(gate.RiskReject, "stale_or_future_market_quote"):
            self.reserve(snapshot(quote_at=(NOW - timedelta(seconds=4)).isoformat()))
        with self.assertRaisesRegex(gate.RiskReject, "stale_or_future_account_snapshot"):
            self.reserve(snapshot(snapshot_at=(NOW + timedelta(seconds=1)).isoformat()))

    def test_daily_drawdown_latches_even_if_subsequent_equity_recovers(self):
        first = self.reserve(snapshot(equity_cash="9800"))
        self.assertTrue(first["circuit_breaker_latched"])
        self.assertEqual(first["decisions"][0]["status"], "REJECTED")
        second = self.reserve(snapshot([leg("r2")], equity_cash="10000"))
        self.assertTrue(second["circuit_breaker_latched"])
        self.assertEqual(second["decisions"][0]["reasons"], ["risk_circuit_breaker_latched"])

    def test_peak_drawdown_and_loss_streak_stop(self):
        for trigger in ({"peak_equity_cash": "11000"}, {"consecutive_losses": 4}):
            with self.subTest(trigger=trigger), tempfile.TemporaryDirectory() as td:
                private = Path(td) / "private"
                private.mkdir(mode=0o700)
                result = gate.reserve_research_slots(snapshot(**trigger), private / "risk.db", now=NOW)
                self.assertEqual(result["decisions"][0]["status"], "REJECTED")
                self.assertTrue(result["circuit_breaker_latched"])

    def test_day_anchor_reset_and_time_replay_are_refused(self):
        self.reserve(snapshot())
        with self.assertRaisesRegex(gate.RiskReject, "day_start_anchor_reset_attempt"):
            self.reserve(snapshot([leg("r2")], day_start_equity_cash="11000",
                                  peak_equity_cash="12000"))
        with self.assertRaisesRegex(gate.RiskReject, "snapshot_timestamp_regression"):
            self.reserve(snapshot([leg("r3")], snapshot_at=(NOW - timedelta(seconds=1)).isoformat(),
                                  quote_at=(NOW - timedelta(seconds=2)).isoformat()))

    def test_unsupported_symbol_missing_adverse_stop_and_underbuffer_refused(self):
        variations = [dict(symbol="XYZUSD"), dict(stop="1.2000"),
                      dict(execution_buffer_cash="0")]
        for changes in variations:
            with self.subTest(changes=changes):
                proposed = leg()
                proposed.update(changes)
                with self.assertRaises(gate.RiskReject):
                    self.reserve(snapshot([proposed]))

    def test_symbol_and_cluster_are_separate_from_strategy_risk(self):
        group = [leg("a", strategy="shared", qty="4000"),
                 leg("b", symbol="GBPUSD", strategy="shared", qty="40"),
                 leg("c", symbol="USDJPY", strategy="shared", qty="40")]
        result = self.reserve(snapshot(group))
        self.assertEqual(result["decisions"][0]["status"], "RESEARCH_SLOT_RESERVED")
        self.assertEqual(result["decisions"][1]["status"], "RESEARCH_SLOT_RESERVED")
        self.assertEqual(result["decisions"][2]["status"], "REJECTED")
        self.assertIn("strategy_concentration_budget", result["decisions"][2]["reasons"])

    def test_unsafe_directory_or_symlink_db_rejected(self):
        os.chmod(self.private, 0o755)
        with self.assertRaisesRegex(gate.RiskReject, "private_directory"):
            self.reserve(snapshot())
        os.chmod(self.private, 0o700)
        target = self.private / "real.db"
        target.touch(mode=0o600)
        self.db.symlink_to(target)
        with self.assertRaisesRegex(gate.RiskReject, "symlink"):
            self.reserve(snapshot())

    def test_bounded_audit_history_never_deletes_or_overwrites_prior_receipts(self):
        self.reserve(snapshot([leg("first")]))
        with patch.object(gate, "MAX_HISTORY_ROWS", 1):
            with self.assertRaisesRegex(gate.RiskReject, "history_budget"):
                self.reserve(snapshot([leg("second")]))
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT request_id FROM decisions").fetchall(),
                             [("first",)])

    def test_atomic_rollback_of_prior_proposal_on_later_reused_id(self):
        self.reserve(snapshot([leg("known")]))
        payload = snapshot([leg("new"), leg("known", qty="2000")])
        with self.assertRaisesRegex(gate.RiskReject, "request_id_reused"):
            self.reserve(payload)
        with sqlite3.connect(self.db) as con:
            ids = [row[0] for row in con.execute("SELECT request_id FROM decisions ORDER BY request_id")]
        self.assertEqual(ids, ["known"])


if __name__ == "__main__":
    unittest.main()
