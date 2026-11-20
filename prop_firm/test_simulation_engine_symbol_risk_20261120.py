from decimal import Decimal as D
import unittest
from prop_firm.simulation_engine import SimulationEngine, OrderRequest, MarketQuote


def quote(symbol, bid, ask, sequence):
    return MarketQuote(symbol, D(bid), D(ask), "2026-11-20T00:00:00Z", sequence)


def buy(order_id, symbol="A", *, limit=None):
    return OrderRequest(order_id, symbol, "buy", D("1"),
                        order_type="limit" if limit is not None else "market",
                        limit_price=D(limit) if limit is not None else None,
                        stop_loss=D("90"))


class SimulationSymbolRiskTests(unittest.TestCase):
    def test_other_symbol_cannot_reprice_position(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        before=e.snapshot()
        e.process_quote(quote("B","1000","1001",2))
        self.assertEqual(e.snapshot(),before)

    def test_other_symbol_cannot_trigger_pending(self):
        e=SimulationEngine()
        e.submit(buy("a",limit="99"),quote("A","100","101",1))
        self.assertEqual(e.process_quote(quote("B","97","98",2)),[])
        self.assertEqual(e.snapshot().pending_count,1)
        self.assertEqual(e.process_quote(quote("A","97","98",3))[0].status,"filled")

    def test_breach_cancels_pending_before_fill(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        e.submit(buy("b","B",limit="99"),quote("B","100","101",2))
        results=e.process_quote(quote("A","30","31",3))
        self.assertTrue(e.snapshot().blocked)
        self.assertEqual([x.reason for x in results],["stop_loss","account_blocked"])
        self.assertEqual(e.snapshot().pending_count,0)
        self.assertEqual(e.snapshot().position_count,0)
        self.assertEqual(e.snapshot().realized_pnl,D("-71"))
        self.assertEqual(e.process_quote(quote("B","97","98",4)),[])

    def test_submit_marks_existing_positions_before_risk_admission(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        result=e.submit(buy("b"),quote("A","30","31",2))
        self.assertEqual(result.reason,"account_blocked")
        self.assertTrue(e.snapshot().blocked)

    def test_close_marks_other_positions_of_same_symbol(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        e.submit(buy("b"),quote("A","100","101",2))
        e.close("a",quote("A","95","96",3))
        self.assertEqual(e.snapshot().realized_pnl,D("-6"))
        self.assertEqual(e.snapshot().floating_pnl,D("-6"))

    def test_closed_order_id_cannot_be_reused(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        e.close("a",quote("A","100","101",2))
        self.assertEqual(e.submit(buy("a"),quote("A","100","101",3)).reason,
                         "duplicate_order_id")

    def test_quote_sequence_rules_preserved(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        with self.assertRaises(ValueError):
            e.process_quote(quote("A","100","101",1))


    def test_long_stop_uses_bid_at_gap(self):
        e=SimulationEngine(commission_per_unit=D("1"))
        e.submit(buy("a"),quote("A","100","101",1))
        results=e.process_quote(quote("A","85","86",2))
        self.assertEqual([(x.reason,x.price) for x in results],[("stop_loss",D("85"))])
        self.assertEqual(e.snapshot().realized_pnl,D("-17"))

    def test_long_target(self):
        e=SimulationEngine()
        o=OrderRequest("a","A","buy",D("1"),stop_loss=D("90"),take_profit=D("110"))
        e.submit(o,quote("A","100","101",1))
        self.assertEqual(e.process_quote(quote("A","109","110",2)),[])
        result=e.process_quote(quote("A","112","113",3))[0]
        self.assertEqual((result.reason,result.price),("take_profit",D("112")))

    def test_short_stop_uses_ask(self):
        e=SimulationEngine()
        o=OrderRequest("a","A","sell",D("1"),stop_loss=D("110"),take_profit=D("90"))
        e.submit(o,quote("A","100","101",1))
        result=e.process_quote(quote("A","109","110",2))[0]
        self.assertEqual((result.reason,result.price),("stop_loss",D("110")))

    def test_short_target_uses_ask(self):
        e=SimulationEngine()
        o=OrderRequest("a","A","sell",D("1"),stop_loss=D("110"),take_profit=D("90"))
        e.submit(o,quote("A","100","101",1))
        self.assertEqual(e.process_quote(quote("A","89","91",2)),[])
        self.assertEqual(e.process_quote(quote("A","88","89",3))[0].reason,"take_profit")

    def test_invalid_bracket_rejected_at_entry(self):
        e=SimulationEngine()
        o=OrderRequest("a","A","buy",D("1"),stop_loss=D("90"),take_profit=D("100"))
        self.assertEqual(e.submit(o,quote("A","100","101",1)).reason,"invalid_protection_bracket")
        self.assertEqual(e.snapshot().position_count,0)

    def test_pending_gap_invalid_bracket_rejected(self):
        e=SimulationEngine()
        e.submit(buy("a",limit="99"),quote("A","100","101",1))
        result=e.process_quote(quote("A","85","86",2))[0]
        self.assertEqual(result.reason,"invalid_protection_bracket")
        self.assertEqual(e.snapshot().position_count,0)

    def test_manual_close_does_not_duplicate_protective_exit(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        result=e.close("a",quote("A","89","90",2))
        self.assertEqual(result.reason,"stop_loss")
        self.assertEqual(e.snapshot().closed_trade_count,1)

    def test_other_symbol_does_not_trigger_protection(self):
        e=SimulationEngine()
        e.submit(buy("a"),quote("A","100","101",1))
        self.assertEqual(e.process_quote(quote("B","10","11",2)),[])
        self.assertEqual(e.snapshot().position_count,1)
