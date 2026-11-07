"""Offline provenance and shared research risk bridge contract tests."""

import copy
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_research_handoff.py"
SOURCE = REPO if REPO.is_file() else Path(__file__).with_name("mojtrade_research_handoff.py")
spec = importlib.util.spec_from_file_location("mojtrade_research_handoff", SOURCE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
NOW = datetime(2026, 11, 7, 18, tzinfo=timezone.utc)


def birth_report(symbol="EUR/USD"):
    program = {"operator": "ALL", "side": "BUY", "hold_bars": 3, "stop_atr": 2.0,
               "conditions": [{"feature": "momentum", "window": 6,
                               "comparison": "GT", "threshold": .1},
                              {"feature": "range_location", "window": 12,
                               "comparison": "GT", "threshold": .1}]}
    birth = {"strategy_id": "MTF-0123456789abcdef01234567",
             "generator_version": bridge.FOUNDRY_SCHEMA,
             "program": program, "ast_hash": bridge._hash(program),
             "state": "RESEARCH_ONLY_UNPROVEN", "broker_eligible": False,
             "execution": "disabled", "orders": 0,
             "data_digest": "research-digest", "source_id": "verified-candle-export",
             "trial_number": 1}
    birth["receipt_sha256"] = bridge._hash(birth)
    report = {"schema": bridge.FOUNDRY_SCHEMA, "mode": "RESEARCH_ONLY",
              "execution": "disabled", "orders": 0, "public_signals": 0,
              "symbol": symbol, "dataset_digest": "research-digest",
              "dataset_source_id": "verified-candle-export",
              "multiple_testing_gate": {"status": "NOT_STATISTICALLY_VALIDATED",
                                        "eligible_for_broker_or_public_signals": False},
              "birth_certificates": [birth],
              "trial_ledger": [{"trial": 1, "state": "BORN_RESEARCH_ONLY",
                                "strategy_id": birth["strategy_id"]}]}
    report["report_sha256"] = bridge._hash(report)
    return report


def risk_context(mode="DEMO", quote_seconds=-1):
    return {"account_id": "demo-shadow", "account_mode": mode,
            "risk_day": NOW.date().isoformat(), "snapshot_at": NOW.isoformat(),
            "quote_at": (NOW + timedelta(seconds=quote_seconds)).isoformat(),
            "equity_cash": "10000", "day_start_equity_cash": "10000",
            "peak_equity_cash": "10000", "consecutive_losses": 0,
            "open_positions": []}


def trade(qty="1000", stop="1.0950"):
    return {"quantity": qty, "entry": "1.1000", "stop": stop,
            "unit_value_cash_per_price_point": "1", "execution_buffer_cash": "1"}


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private = Path(self.tmp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.db = self.private / "risk.sqlite3"
        self.report = birth_report()
        self.id = self.report["birth_certificates"][0]["strategy_id"]

    def tearDown(self):
        self.tmp.cleanup()

    def do_handoff(self, *, report=None, context=None, proposal=None, ident=None):
        return bridge.handoff(report if report is not None else self.report,
                              ident or self.id, context if context is not None else risk_context(),
                              proposal if proposal is not None else trade(), self.db, now=NOW)

    def test_real_risk_engine_receives_valid_birth_and_reserves_without_orders(self):
        handoff = self.do_handoff()
        self.assertEqual(handoff["mapped_symbol"], "EURUSD")
        self.assertEqual(handoff["mode"], "RESEARCH_ONLY")
        self.assertEqual(handoff["orders"], 0)
        self.assertEqual(handoff["public_signals"], 0)
        self.assertFalse(handoff["broker_eligible"])
        receipt = handoff["risk_response"]["decisions"][0]
        self.assertEqual(receipt["status"], "RESEARCH_SLOT_RESERVED")
        self.assertEqual(handoff["handoff_sha256"], bridge._hash(
            {k: v for k, v in handoff.items() if k != "handoff_sha256"}))

    def test_actual_foundry_contract_when_foundry_pr_is_present(self):
        src = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_strategy_foundry.py"
        fixture = Path(__file__).resolve().parents[1] / "tests" / "test_mojtrade_strategy_foundry.py"
        if not src.is_file():
            src = Path(__file__).with_name("mojtrade_strategy_foundry.py")
            fixture = Path(__file__).with_name("test_mojtrade_strategy_foundry.py")
        if not src.is_file() or not fixture.is_file():
            self.skipTest("foundry PR #2120 not present on this independent branch")
        fspec = importlib.util.spec_from_file_location("foundry_reference", src)
        foundry = importlib.util.module_from_spec(fspec)
        fspec.loader.exec_module(foundry)
        tspec = importlib.util.spec_from_file_location("foundry_test_fixture", fixture)
        fixture_module = importlib.util.module_from_spec(tspec)
        tspec.loader.exec_module(fixture_module)
        report = foundry.invent(fixture_module.market_data(), seed=173, max_trials=12)
        cert = report["birth_certificates"][0]
        stop = "99" if cert["program"]["side"] == "BUY" else "101"
        result = self.do_handoff(report=report, ident=cert["strategy_id"],
                                 proposal={"quantity": "0.1", "entry": "100",
                                           "stop": stop,
                                           "unit_value_cash_per_price_point": "1",
                                           "execution_buffer_cash": "1"})
        self.assertEqual(result["mapped_symbol"], "BTCUSD")
        self.assertEqual(result["orders"], 0)
        self.assertEqual(result["risk_response"]["decisions"][0]["status"],
                         "RESEARCH_SLOT_RESERVED")

    def test_same_birth_and_quote_is_idempotent_across_calls(self):
        first = self.do_handoff()
        again = self.do_handoff()
        self.assertEqual(first, again)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1)

    def test_same_snapshot_quote_with_changed_trade_cannot_reuse_identity(self):
        self.do_handoff()
        with self.assertRaisesRegex(bridge.HandoffReject, "request_id_reused"):
            self.do_handoff(proposal=trade(qty="1500"))
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1)

    def test_a_distinct_quote_creates_new_risk_reservation_not_same_id(self):
        first = self.do_handoff()
        second = self.do_handoff(context=risk_context(quote_seconds=-2))
        self.assertNotEqual(first["risk_response"]["decisions"][0]["request_id"],
                            second["risk_response"]["decisions"][0]["request_id"])
        self.assertEqual(second["risk_response"]["decisions"][0]["status"],
                         "RESEARCH_SLOT_RESERVED")
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 2)

    def test_report_or_birth_mutation_without_new_checksum_rejected(self):
        for mutation in ("symbol", "cert_side", "cert_id"):
            modified = copy.deepcopy(self.report)
            if mutation == "symbol":
                modified["symbol"] = "GBP/USD"
            elif mutation == "cert_side":
                modified["birth_certificates"][0]["program"]["side"] = "SELL"
            else:
                modified["birth_certificates"][0]["strategy_id"] = "MTF-hijacked"
            with self.subTest(mutation=mutation), self.assertRaises(bridge.HandoffReject):
                self.do_handoff(report=modified)
        self.assertFalse(self.db.exists())

    def test_rehashed_birth_with_wrong_trial_ledger_and_source_rejected(self):
        modified = copy.deepcopy(self.report)
        modified["birth_certificates"][0]["source_id"] = "forged-source"
        cert = modified["birth_certificates"][0]
        cert["receipt_sha256"] = bridge._hash({k: v for k, v in cert.items()
                                               if k != "receipt_sha256"})
        modified["report_sha256"] = bridge._hash({k: v for k, v in modified.items()
                                                 if k != "report_sha256"})
        with self.assertRaisesRegex(bridge.HandoffReject, "candidate_provenance"):
            self.do_handoff(report=modified)
        other = copy.deepcopy(self.report)
        other["trial_ledger"] = []
        other["report_sha256"] = bridge._hash({k: v for k, v in other.items()
                                               if k != "report_sha256"})
        with self.assertRaisesRegex(bridge.HandoffReject, "trial_ledger"):
            self.do_handoff(report=other)

    def test_statistical_nonvalidation_gate_must_be_present(self):
        unsafe = copy.deepcopy(self.report)
        unsafe["multiple_testing_gate"]["status"] = "APPROVED"
        unsafe["report_sha256"] = bridge._hash({k: v for k, v in unsafe.items()
                                                if k != "report_sha256"})
        with self.assertRaisesRegex(bridge.HandoffReject, "statistical_gate"):
            self.do_handoff(report=unsafe)

    def test_no_live_account_passes_to_shared_risk_db(self):
        with self.assertRaisesRegex(bridge.HandoffReject, "non_demo"):
            self.do_handoff(context=risk_context(mode="LIVE"))
        self.assertFalse(self.db.exists())

    def test_invalid_or_mismatched_side_stop_is_rejected(self):
        with self.assertRaisesRegex(bridge.HandoffReject, "shared_risk_gate:stop_not_adverse"):
            self.do_handoff(proposal=trade(stop="1.2"))
        self.assertFalse(self.db.exists())

    def test_unknown_symbol_and_missing_candidate_blocked_before_db(self):
        unknown = birth_report("DOGE/USD")
        with self.assertRaisesRegex(bridge.HandoffReject, "unmapped_research_symbol"):
            self.do_handoff(report=unknown)
        with self.assertRaisesRegex(bridge.HandoffReject, "candidate_not_unique"):
            self.do_handoff(ident="MTF-this-does-not-exist")
        self.assertFalse(self.db.exists())

    def test_wrong_request_and_trade_shapes_fail_closed(self):
        invalid = trade()
        invalid["execute_market_order"] = True
        with self.assertRaisesRegex(bridge.HandoffReject, "trade_hypothesis_schema"):
            self.do_handoff(proposal=invalid)
        bad_context = risk_context()
        bad_context["proposals"] = []
        with self.assertRaisesRegex(bridge.HandoffReject, "risk_context_schema"):
            self.do_handoff(context=bad_context)
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
