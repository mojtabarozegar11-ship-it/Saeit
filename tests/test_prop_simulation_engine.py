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

    def test_unrelated_quote_does_not_reprice_position(self):
        e = SimulationEngine()
        e.submit(order("a"), q(1))
        equity = e.snapshot().equity
        e.process_quote(MarketQuote("XAUUSD", D("2000"), D("2001"), "2026-11-19T00:00:02Z", 2))
        self.assertEqual(e.snapshot().equity, equity)

    def test_unrelated_quote_does_not_trigger_pending_order(self):
        e = SimulationEngine()
        e.submit(order("a", kind="limit", limit="99", stop="98"), q(1))
        result = e.process_quote(MarketQuote("XAUUSD", D("98"), D("99"), "2026-11-19T00:00:02Z", 2))
        self.assertEqual(result, [])
        self.assertEqual(e.snapshot().pending_count, 1)
        self.assertEqual(e.snapshot().position_count, 0)

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

    def test_gap_through_stop_uses_executable_bid(self):
        e = SimulationEngine()
        e.submit(order("a", stop="99"), q(1))
        result = e.process_quote(q(2, bid="97", ask="98"))
        self.assertEqual(result[0].reason, "stop_loss")
        self.assertEqual(result[0].price, D("97"))
        self.assertEqual(e.snapshot().realized_pnl, D("-4"))
        self.assertEqual(e.snapshot().position_count, 0)

    def test_take_profit_uses_executable_price(self):
        e = SimulationEngine()
        e.submit(OrderRequest("a", "EURUSD", "buy", D("1"), stop_loss=D("99"),
                              take_profit=D("103")), q(1))
        result = e.process_quote(q(2, bid="104", ask="105"))
        self.assertEqual(result[0].reason, "take_profit")
        self.assertEqual(e.snapshot().realized_pnl, D("3"))

    def test_sell_stop_uses_ask(self):
        e = SimulationEngine()
        e.submit(order("a", side="sell", stop="102"), q(1))
        result = e.process_quote(q(2, bid="102", ask="103"))
        self.assertEqual(result[0].reason, "stop_loss")
        self.assertEqual(e.snapshot().realized_pnl, D("-3"))

    def test_closed_order_id_cannot_reopen(self):
        e = SimulationEngine()
        e.submit(order("a"), q(1))
        e.close("a", q(2, bid="103", ask="104"))
        self.assertEqual(e.submit(order("a"), q(3)).reason, "duplicate_order_id")

    def test_drawdown_blocks_pending_fill(self):
        e = SimulationEngine()
        e.submit(order("a", stop="99", quantity="10"), q(1))
        e.submit(order("b", kind="limit", limit="99", stop="80"), q(2))
        result = e.process_quote(q(3, bid="90", ask="91"))
        self.assertTrue(e.snapshot().blocked)
        self.assertEqual(e.snapshot().position_count, 0)
        self.assertEqual(e.snapshot().pending_count, 0)
        self.assertEqual(result[-1].reason, "account_blocked")

    def test_pending_gap_past_protective_stop_is_rejected(self):
        e = SimulationEngine()
        e.submit(order("a", kind="limit", limit="99", stop="98"), q(1))
        result = e.process_quote(q(2, bid="96", ask="97"))
        self.assertEqual(result[0].reason, "invalid_protective_stop_at_fill")
        self.assertEqual(e.snapshot().position_count, 0)

    def test_new_utc_day_carries_last_mark_and_keeps_fixed_daily_allowance(self):
        e = SimulationEngine()
        e.submit(order("a", stop="99"), q(1))
        e.close("a", q(2, bid="103", ask="104"))
        self.assertEqual(e.realized_by_day["2026-11-19"], D("2"))
        e.process_quote(MarketQuote("EURUSD", D("100"), D("101"), "2026-11-20T00:00:01Z", 3))
        self.assertEqual(e.day_open_equity, D("1002"))
        self.assertEqual(e.daily_floor, D("942"))

    def test_overnight_gap_is_not_erased_by_daily_reset(self):
        e = SimulationEngine()
        e.submit(order("a", stop="99", quantity="10"), q(1))
        e.process_quote(MarketQuote("EURUSD", D("90"), D("91"), "2026-11-20T00:00:01Z", 2))
        self.assertEqual(e.day_open_equity, D("990"))
        self.assertEqual(e.realized_by_day["2026-11-20"], D("-110"))
        self.assertTrue(e.snapshot().blocked)

    def test_quote_time_cannot_move_backwards_even_with_higher_sequence(self):
        e = SimulationEngine()
        e.submit(order("a"), q(2))
        with self.assertRaises(ValueError):
            e.process_quote(q(1).__class__("EURUSD", D("100"), D("101"),
                                           "2026-11-19T00:00:01Z", 3))
        self.assertEqual(e.last_quote_sequence, 2)

    def test_new_day_cannot_clear_drawdown_breach(self):
        e = SimulationEngine()
        e.submit(order("a", stop="99", quantity="10"), q(1))
        e.process_quote(q(2, bid="90", ask="91"))
        e.process_quote(MarketQuote("EURUSD", D("100"), D("101"), "2026-11-20T00:00:01Z", 3))
        self.assertTrue(e.snapshot().blocked)
        self.assertEqual(e.submit(order("b"), MarketQuote("EURUSD", D("100"), D("101"),
                         "2026-11-20T00:00:02Z", 4)).reason, "account_blocked")

    def test_real_side_effects_are_impossible(self):
        e = SimulationEngine()
        self.assertFalse(hasattr(e, "broker_client"))
        self.assertFalse(hasattr(e, "submit_live_order"))


if __name__ == "__main__":
    unittest.main()
