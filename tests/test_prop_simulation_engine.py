import unittest
from decimal import Decimal as D

from prop_firm.simulation_engine import (
    MarketQuote, OrderRequest, SimulationEngine,
)


def q(seq, bid="100", ask="101"):
    return MarketQuote("EURUSD", D(bid), D(ask), f"2026-11-19T00:00:{seq:02d}Z", seq)


def order(oid, side="buy", stop="99", kind="market", limit=None, stop_price=None, quantity="1"):
    return OrderRequest(
        order_id=oid, symbol="EURUSD", side=side, quantity=D(quantity),
        order_type=kind, limit_price=None if limit is None else D(limit),
        stop_price=None if stop_price is None else D(stop_price),
        stop_loss=D(stop),
    )


class SimulationEngineTests(unittest.TestCase):
    def test_market_fill_and_snapshot(self):
        e = SimulationEngine()
        result = e.submit(order("a"), q(1))
        self.assertEqual(result.status, "filled")
        self.assertEqual(e.snapshot().position_count, 1)
        self.assertEqual(e.snapshot().open_risk, D("2"))

    def test_per_trade_cap(self):
        e = SimulationEngine()
        self.assertEqual(e.submit(order("a", stop="70"), q(1)).reason,
                         "per_trade_risk_limit")

    def test_aggregate_cap(self):
        e = SimulationEngine()
        self.assertEqual(e.submit(order("a", stop="99", quantity="10"), q(1)).status, "filled")
        self.assertEqual(e.submit(order("b", stop="99", quantity="12.5"), q(2)).reason,
                         "aggregate_open_risk_limit")

    def test_pending_limit_fills(self):
        e = SimulationEngine()
        result = e.submit(order("a", kind="limit", limit="99", stop="98"), q(1))
        self.assertEqual(result.status, "pending")
        filled = e.process_quote(q(2, bid="98", ask="99"))
        self.assertEqual(filled[0].status, "filled")

    def test_pending_stop_fills(self):
        e = SimulationEngine()
        result = e.submit(order("a", kind="stop", stop="99", stop_price="102"), q(1))
        self.assertEqual(result.status, "pending")
        filled = e.process_quote(q(2, bid="101", ask="102"))
        self.assertEqual(filled[0].status, "filled")

    def test_close_profit(self):
        e = SimulationEngine()
        e.submit(order("a"), q(1))
        result = e.close("a", q(2, bid="103", ask="104"))
        self.assertEqual(result.status, "closed")
        self.assertEqual(e.snapshot().closed_trade_count, 1)
        self.assertGreater(e.snapshot().realized_pnl, D("0"))

    def test_stale_quote_rejected(self):
        e = SimulationEngine()
        self.assertEqual(e.submit(order("a"), q(2)).status, "filled")
        self.assertEqual(e.submit(order("b"), q(1)).reason, "stale_quote")

    def test_duplicate_rejected(self):
        e = SimulationEngine()
        e.submit(order("a"), q(1))
        self.assertEqual(e.submit(order("a"), q(2)).reason, "duplicate_order_id")

    def test_no_stop_is_rejected(self):
        with self.assertRaises(ValueError):
            OrderRequest("a", "EURUSD", "buy", D("1"))

    def test_real_side_effects_are_impossible(self):
        e = SimulationEngine()
        self.assertFalse(hasattr(e, "broker_client"))
        self.assertFalse(hasattr(e, "submit_live_order"))


if __name__ == "__main__":
    unittest.main()
