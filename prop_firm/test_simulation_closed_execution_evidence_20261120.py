from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal as D
import unittest

from prop_firm.simulation_engine import MarketQuote, OrderRequest, SimulationEngine


def q(symbol, bid, ask, seq, time="2026-11-20T00:00:00Z"):
    return MarketQuote(symbol, D(bid), D(ask), time, seq)


def order(ref, side="buy"):
    return OrderRequest(ref, "A", side, D("1"),
                        stop_loss=D("90" if side == "buy" else "110"),
                        take_profit=D("110" if side == "buy" else "90"))


class ClosedExecutionEvidenceTests(unittest.TestCase):
    def test_net_accounting_and_utc_times(self):
        e=SimulationEngine(commission_per_unit=D("0.25"))
        e.submit(order("a"),q("A","100","101",1,"2026-11-20T04:00:00+04:00"))
        e.close("a",q("A","105","106",2,"2026-11-20T00:01:00Z"))
        record,=e.closed_execution_records
        self.assertEqual((record.entry_price,record.exit_price),(D("101"),D("105")))
        self.assertEqual((record.gross_pnl,record.commission,record.net_pnl),(D("4"),D("0.25"),D("3.75")))
        self.assertEqual(record.opened_at,datetime(2026,11,20,tzinfo=timezone.utc))
        self.assertEqual(record.closed_at,datetime(2026,11,20,0,1,tzinfo=timezone.utc))
        self.assertEqual((record.opened_sequence,record.closed_sequence),(1,2))
        self.assertEqual(e.snapshot().realized_pnl,record.net_pnl)

    def test_records_are_immutable(self):
        e=SimulationEngine()
        e.submit(order("a"),q("A","100","101",1))
        e.close("a",q("A","106","107",2))
        with self.assertRaises(FrozenInstanceError):
            e.closed_execution_records[0].net_pnl=D("999")

    def test_protection_records_multiple_closes_at_same_quote(self):
        e=SimulationEngine()
        e.submit(order("a"),q("A","100","101",1))
        e.submit(order("b"),q("A","100","101",2))
        e.process_quote(q("A","111","112",3))
        self.assertEqual([x.order_id for x in e.closed_execution_records],["a","b"])
        self.assertEqual([x.closed_sequence for x in e.closed_execution_records],[3,3])
        self.assertEqual([x.reason for x in e.closed_execution_records],["take_profit","take_profit"])
        self.assertEqual(sum(x.net_pnl for x in e.closed_execution_records),e.snapshot().realized_pnl)

    def test_short_protective_record(self):
        e=SimulationEngine()
        e.submit(order("a","sell"),q("A","100","101",1))
        e.process_quote(q("A","88","89",2))
        r,=e.closed_execution_records
        self.assertEqual((r.side,r.exit_price,r.net_pnl,r.reason),("sell",D("89"),D("11"),"take_profit"))

    def test_regressed_timestamp_leaves_state_intact(self):
        e=SimulationEngine()
        e.submit(order("a"),q("A","100","101",1,"2026-11-20T00:01:00Z"))
        before=e.snapshot()
        for action in (
            lambda: e.process_quote(q("A","89","90",2)),
            lambda: e.close("a",q("A","89","90",2)),
            lambda: e.submit(order("b"),q("A","89","90",2)),
        ):
            with self.assertRaises(ValueError):
                action()
            self.assertEqual(e.snapshot(),before)
            self.assertEqual(e.last_quote_sequence,1)
            self.assertEqual(e.closed_execution_records,())

    def test_invalid_timestamp_and_sequence(self):
        for t in ("2026-11-20","2026-11-20T00:00:00","invalid"):
            with self.assertRaises(ValueError):
                q("A","100","101",1,t)
        for seq in (True,1.5,-1):
            with self.assertRaises(ValueError):
                q("A","100","101",seq)
