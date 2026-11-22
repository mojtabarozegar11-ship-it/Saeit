"""End-to-end research-only tests of all four MojTrade engines together."""

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "scripts" / "mojtrade_unified_shadow.py"
FIX = REPO / "tests" / "test_mojtrade_strategy_foundry.py"
if not SRC.is_file():
    SRC = Path(__file__).with_name("mojtrade_unified_shadow.py")
    FIX = Path(__file__).with_name("test_mojtrade_strategy_foundry.py")
sys.path.insert(0, str(SRC.parent))
spec = importlib.util.spec_from_file_location("mojtrade_unified_shadow", SRC)
shadow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)
fspec = importlib.util.spec_from_file_location("foundry_market_fixture", FIX)
fixture_module = importlib.util.module_from_spec(fspec)
fspec.loader.exec_module(fixture_module)


def packet():
    bars = fixture_module.market_data()
    last = bars["bars"][-1]
    decision = datetime.fromisoformat(last["available_at"])
    close = Decimal(str(last["close"]))
    def price(offset):
        return str((close + Decimal(offset)).quantize(Decimal("0.00000001")))
    first = {"t": decision.isoformat(), "available_at": decision.isoformat(),
             "venue_status": "OPEN",
             "bids": [{"price": price("-0.1"), "size": "5"}],
             "asks": [{"price": price("0.1"), "size": "5"}]}
    second_time = decision + timedelta(milliseconds=100)
    second = {"t": second_time.isoformat(), "available_at": second_time.isoformat(),
              "venue_status": "OPEN",
              "bids": [{"price": price("-0.15"), "size": "5"}],
              "asks": [{"price": price("0.15"), "size": "5"}]}
    report = {
        "market_bars": bars,
        "execution_book": {"schema": shadow.twin.SCHEMA, "source_id": "synthetic-quotes",
                           "symbol": "BTCUSD", "events": [first, second]},
        "risk_context": {"account_id": "demo-unified", "account_mode": "DEMO",
                         "risk_day": decision.date().isoformat(),
                         "snapshot_at": decision.isoformat(),
                         "quote_at": decision.isoformat(),
                         "equity_cash": "10000", "day_start_equity_cash": "10000",
                         "peak_equity_cash": "10000", "consecutive_losses": 0,
                         "open_positions": []},
        "hypothetical_size": {
            "quantity": "1", "unit_value_cash_per_price_point": "1",
            "execution_buffer_cash": "1", "client_latency_ms": 10,
            "network_latency_ms": 0, "venue_latency_ms": 0, "ttl_ms": 200,
            "time_in_force": "IOC", "max_adverse_slippage_bps": "100",
            "commission_bps_per_side": "2"},
        "candidate_id": None, "seed": 173, "trials": 64,
        "research_fee_bps": 2.0,
    }
    return report, decision


class UnifiedShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private = Path(self.tmp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.request, self.now = packet()

    def tearDown(self):
        self.tmp.cleanup()

    def run_shadow(self, request=None, now=None):
        return shadow.run_shadow(request if request is not None else self.request,
                                 self.private, now=now or self.now)

    def test_e2e_invention_closed_signal_risk_reservation_and_depth_replay(self):
        report = self.run_shadow()
        self.assertEqual(report["status"], "RESEARCH_EXECUTION_REPLAYED")
        self.assertEqual(report["real_orders"], 0)
        self.assertEqual(report["public_signals"], 0)
        self.assertFalse(report["broker_eligible"])
        self.assertEqual(report["risk_handoff"]["risk_response"]["decisions"][0]
                         ["status"], "RESEARCH_SLOT_RESERVED")
        self.assertEqual(report["execution_twin"]["hypothetical_intents_evaluated"], 1)
        self.assertEqual(report["execution_twin"]["real_orders"], 0)
        self.assertEqual(report["report_sha256"], shadow._hash(
            {k: v for k, v in report.items() if k != "report_sha256"}))

    def test_identical_replay_preserves_one_invention_and_one_risk_record(self):
        first = self.run_shadow()
        second = self.run_shadow()
        self.assertEqual(first, second)
        self.assertEqual(shadow.foundry.verify_private_registry(
            self.private / "unified-foundry-registry.jsonl")["records"], 1)

    def test_stale_closed_bar_is_rejected_before_any_disk_writes(self):
        request = copy.deepcopy(self.request)
        newer = self.now + timedelta(seconds=10)
        for ev in request["execution_book"]["events"]:
            at = datetime.fromisoformat(ev["t"]) + timedelta(seconds=10)
            ev["t"] = at.isoformat()
            ev["available_at"] = at.isoformat()
        request["risk_context"]["quote_at"] = newer.isoformat()
        request["risk_context"]["snapshot_at"] = newer.isoformat()
        request["risk_context"]["risk_day"] = newer.date().isoformat()
        with self.assertRaisesRegex(shadow.ShadowReject, "closed_bar_stale"):
            self.run_shadow(request, now=newer)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_cross_source_symbol_mismatch_and_quote_outside_close_rejected(self):
        request = copy.deepcopy(self.request)
        request["execution_book"]["symbol"] = "EURUSD"
        with self.assertRaisesRegex(shadow.ShadowReject, "cross_source_symbol"):
            self.run_shadow(request)
        second = copy.deepcopy(self.request)
        second["execution_book"]["events"][0]["bids"][0]["price"] = "1"
        second["execution_book"]["events"][0]["asks"][0]["price"] = "2"
        with self.assertRaisesRegex(shadow.ShadowReject, "last_candle_close_outside"):
            self.run_shadow(second)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_non_demo_account_rejected_without_ledger(self):
        request = copy.deepcopy(self.request)
        request["risk_context"]["account_mode"] = "LIVE"
        with self.assertRaisesRegex(shadow.ShadowReject, "non_demo_account"):
            self.run_shadow(request)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_inactive_requested_candidate_never_reaches_risk_or_twin(self):
        request = copy.deepcopy(self.request)
        request["candidate_id"] = "MTF-absent-signal-id"
        result = self.run_shadow(request)
        self.assertEqual(result["status"], "NO_CURRENT_RESEARCH_SIGNAL")
        self.assertIsNone(result["risk_handoff"])
        self.assertIsNone(result["execution_twin"])
        self.assertFalse((self.private / "unified-portfolio-risk.sqlite3").exists())

    def test_risk_circuit_breaker_blocks_simulated_execution(self):
        request = copy.deepcopy(self.request)
        request["risk_context"]["equity_cash"] = "9700"
        result = self.run_shadow(request)
        self.assertEqual(result["status"], "RESEARCH_RISK_REFUSED")
        self.assertTrue(result["risk_handoff"]["risk_response"]["circuit_breaker_latched"])
        self.assertIsNone(result["execution_twin"])
        self.assertEqual(result["real_orders"], 0)

    def test_invalid_twin_parameter_preflight_does_not_strand_risk_reservation(self):
        request = copy.deepcopy(self.request)
        request["hypothetical_size"]["time_in_force"] = "LIVE_MARKET_ORDER"
        with self.assertRaisesRegex(shadow.ShadowReject, "execution_twin_preflight"):
            self.run_shadow(request)
        self.assertFalse((self.private / "unified-portfolio-risk.sqlite3").exists())

    def test_future_closed_bar_unobservable_and_old_snapshot_refused(self):
        request = copy.deepcopy(self.request)
        request["market_bars"]["bars"][-1]["available_at"] = (
            self.now + timedelta(seconds=3)).isoformat()
        with self.assertRaisesRegex(shadow.ShadowReject, "closed_bar_stale"):
            self.run_shadow(request)
        old = copy.deepcopy(self.request)
        old["risk_context"]["snapshot_at"] = (
            self.now - timedelta(seconds=10)).isoformat()
        with self.assertRaisesRegex(shadow.ShadowReject, "account_quote_not_bound"):
            self.run_shadow(old)

    def test_quote_not_observable_until_after_decision_rejected_without_writes(self):
        request = copy.deepcopy(self.request)
        request["execution_book"]["events"][0]["available_at"] = (
            self.now + timedelta(milliseconds=500)).isoformat()
        with self.assertRaisesRegex(shadow.ShadowReject, "reference_quote_not_yet_observable"):
            self.run_shadow(request)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_caller_cannot_supply_prebuilt_broker_orders_to_unified_chain(self):
        request = copy.deepcopy(self.request)
        request["execution_book"]["hypothetical_intents"] = [{"mode": "LIVE"}]
        with self.assertRaisesRegex(shadow.ShadowReject, "execution_book_schema"):
            self.run_shadow(request)
        self.assertEqual(list(self.private.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
