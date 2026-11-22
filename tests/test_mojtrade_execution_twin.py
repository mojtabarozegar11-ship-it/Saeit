"""Execution twin contracts. All quote books are synthetic, not venue data."""

import copy
import importlib.util
import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


SOURCE_REPO = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_execution_twin.py"
SOURCE = SOURCE_REPO if SOURCE_REPO.is_file() else Path(__file__).with_name("mojtrade_execution_twin.py")
spec = importlib.util.spec_from_file_location("mojtrade_execution_twin", SOURCE)
twin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(twin)
START = datetime(2026, 11, 7, 18, tzinfo=timezone.utc)


def event(ms, *, bid="99.9", ask="100", bid_size="5", ask_size="5",
          halt=False, available_delay_ms=0):
    at = START + timedelta(milliseconds=ms)
    return {"t": at.isoformat(),
            "available_at": (at + timedelta(milliseconds=available_delay_ms)).isoformat(),
            "venue_status": "HALT" if halt else "OPEN",
            "bids": [{"price": bid, "size": bid_size}],
            "asks": [{"price": ask, "size": ask_size}]}


def intent(ident="order-1", *, side="BUY", qty="3", latency=10, ttl=200,
           tif="IOC", slip="100", commission="2", decision_ms=0):
    return {"intent_id": ident, "strategy_id": "research-A", "side": side,
            "quantity": qty, "decision_at": (START + timedelta(milliseconds=decision_ms)).isoformat(),
            "client_latency_ms": latency, "network_latency_ms": 0,
            "venue_latency_ms": 0, "ttl_ms": ttl, "time_in_force": tif,
            "max_adverse_slippage_bps": slip,
            "commission_bps_per_side": commission}


def fixture(intents=None, events=None):
    return {"schema": twin.SCHEMA, "source_id": "synthetic-quote-fixture",
            "symbol": "EURUSD",
            "events": events if events is not None else [
                event(0), event(100, ask="100.1", bid="99.8"),
                event(200, ask="100.2", bid="99.7")],
            "hypothetical_intents": intents if intents is not None else [intent()]}


class ExecutionTwinTests(unittest.TestCase):
    def test_full_ioc_fill_after_latency_uses_ask_and_produces_no_broker_order(self):
        report = twin.replay(fixture())
        receipt = report["receipts"][0]
        self.assertEqual(receipt["status"], "FILLED")
        self.assertEqual(receipt["first_execution_event_index"], 1)
        self.assertEqual(Decimal(receipt["filled_quantity"]), Decimal(3))
        self.assertEqual(Decimal(receipt["average_fill_price"]), Decimal("100.1"))
        self.assertFalse(receipt["broker_order_submitted"])
        self.assertEqual(report["real_orders"], 0)
        self.assertEqual(report["public_signals"], 0)

    def test_two_simultaneous_intents_cannot_both_consume_same_visible_depth(self):
        books = [event(0), event(100, ask_size="5"), event(200)]
        intents = [intent("A", qty="4"), intent("B", qty="4")]
        report = twin.replay(fixture(intents, books))
        self.assertEqual([r["status"] for r in report["receipts"]],
                         ["FILLED", "PARTIAL_CANCELLED"])
        self.assertEqual([Decimal(r["filled_quantity"]) for r in report["receipts"]],
                         [Decimal(4), Decimal(1)])
        self.assertEqual(sum(Decimal(r["filled_quantity"]) for r in report["receipts"]),
                         Decimal(5))

    def test_fok_refusal_does_not_consume_available_depth(self):
        report = twin.replay(fixture([intent("A", qty="6", tif="FOK"),
                                      intent("B", qty="5", tif="IOC")],
                                     [event(0), event(100), event(200)]))
        self.assertEqual(report["receipts"][0]["status"], "FOK_DEPTH_INSUFFICIENT")
        self.assertEqual(report["receipts"][0]["filled_quantity"], "0")
        self.assertEqual(report["receipts"][1]["status"], "FILLED")

    def test_slippage_cap_refuses_price_outside_decision_reference(self):
        scenario = fixture([intent(slip="20")], [event(0), event(100, ask="101"),
                                                   event(200, ask="101")])
        receipt = twin.replay(scenario)["receipts"][0]
        self.assertEqual(receipt["status"], "SLIPPAGE_CAP_OR_NO_LIQUIDITY")
        self.assertEqual(receipt["filled_quantity"], "0")

    def test_latency_after_last_quote_produces_no_executable_event(self):
        scenario = fixture([intent(latency=300, ttl=200)])
        receipt = twin.replay(scenario)["receipts"][0]
        self.assertEqual(receipt["status"], "NO_EXECUTABLE_EVENT")

    def test_ioc_ttl_expires_before_the_first_eligible_market_book(self):
        receipt = twin.replay(fixture([intent(latency=10, ttl=20)]))["receipts"][0]
        self.assertEqual(receipt["status"], "EXPIRED_BEFORE_EXECUTION")

    def test_halted_venue_refuses_new_matching(self):
        report = twin.replay(fixture([intent()], [event(0), event(100, halt=True), event(200)]))
        self.assertEqual(report["receipts"][0]["status"], "VENUE_HALTED")

    def test_unobservable_quote_cannot_be_used_for_decision_reference(self):
        data = fixture()
        data["events"][0]["available_at"] = (START + timedelta(milliseconds=80)).isoformat()
        with self.assertRaisesRegex(twin.TwinReject, "no_observable_reference_quote"):
            twin.replay(data)

    def test_future_quote_change_does_not_change_historical_decision_reference(self):
        before = twin.replay(fixture())["receipts"][0]
        changed = fixture()
        changed["events"][1]["asks"][0]["price"] = "100.4"
        after = twin.replay(changed)["receipts"][0]
        self.assertEqual(before["reference_price"], after["reference_price"])
        self.assertNotEqual(before["average_fill_price"], after["average_fill_price"])

    def test_commission_increase_never_reduces_cost_for_same_fill_path(self):
        low = twin.replay(fixture([intent(commission="1")]))["receipts"][0]
        high = twin.replay(fixture([intent(commission="50")]))["receipts"][0]
        self.assertEqual(low["partial_fills"], high["partial_fills"])
        self.assertGreater(Decimal(high["commission_cash"]), Decimal(low["commission_cash"]))

    def test_sell_hits_bid_and_adverse_slippage_has_positive_cost(self):
        report = twin.replay(fixture([intent(side="SELL", qty="2")]))
        receipt = report["receipts"][0]
        self.assertEqual(receipt["reference_price"], "99.9")
        self.assertEqual(receipt["average_fill_price"], "99.8")
        self.assertGreater(Decimal(receipt["signed_slippage_cost_cash"]), 0)

    def test_invalid_books_and_nonmonotonic_events_fail_closed(self):
        versions = []
        crossed = fixture()
        crossed["events"][1]["bids"][0]["price"] = "101"
        versions.append(crossed)
        duplicate = fixture()
        duplicate["events"][2]["t"] = duplicate["events"][1]["t"]
        versions.append(duplicate)
        invalid = fixture()
        invalid["events"][1]["asks"].append({"price": "99.9", "size": "1"})
        versions.append(invalid)
        negative = fixture()
        negative["events"][1]["asks"][0]["size"] = "-1"
        versions.append(negative)
        for version in versions:
            with self.subTest(variant=versions.index(version)), self.assertRaises(twin.TwinReject):
                twin.replay(version)

    def test_arbitrary_order_types_and_reused_intent_id_are_refused(self):
        with self.assertRaisesRegex(twin.TwinReject, "side_or_tif"):
            twin.replay(fixture([intent(tif="EXECUTE_LIVE")]))
        with self.assertRaisesRegex(twin.TwinReject, "duplicate_intent_id"):
            twin.replay(fixture([intent("same"), intent("same")]))

    def test_replay_is_deterministic_and_all_receipts_hash_verify(self):
        a = twin.replay(fixture([intent("A"), intent("B", qty="7")]))
        b = twin.replay(fixture([intent("A"), intent("B", qty="7")]))
        self.assertEqual(a, b)
        self.assertEqual(a["report_sha256"], twin._digest(
            {k: v for k, v in a.items() if k != "report_sha256"}))
        self.assertTrue(all(r["receipt_sha256"] == twin._digest(
            {k: v for k, v in r.items() if k != "receipt_sha256"}) for r in a["receipts"]))

    def test_partial_execution_remainder_is_cancelled_not_invented_as_filled(self):
        receipt = twin.replay(fixture([intent(qty="7")]))["receipts"][0]
        self.assertEqual(receipt["status"], "PARTIAL_CANCELLED")
        self.assertEqual(Decimal(receipt["filled_quantity"]), Decimal(5))
        self.assertEqual(Decimal(receipt["cancelled_quantity"]), Decimal(2))


if __name__ == "__main__":
    unittest.main()
