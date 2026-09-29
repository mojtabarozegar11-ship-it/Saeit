import pytest
from core.trading_lab import TradingLab


class FakeBroker:
    def __init__(self, name, demo=True):
        self.name, self.demo = name, demo
        self.orders = []
    def equity(self): return 10000.0
    def quote(self, symbol): return 100.0
    def place_demo_order(self, symbol, side, quantity, stop_loss, take_profit):
        self.orders.append((symbol, side, quantity, stop_loss, take_profit))
        return f"demo-{len(self.orders)}"


def test_creates_50_agents_split_across_two_demo_accounts():
    lab = TradingLab({"DEMO_A": FakeBroker("A"), "DEMO_B": FakeBroker("B")})
    assert len(lab.agents) == 50
    assert sum(a.account == "DEMO_A" for a in lab.agents) == 25
    assert sum(a.account == "DEMO_B" for a in lab.agents) == 25


def test_live_adapter_is_blocked():
    with pytest.raises(RuntimeError, match="LIVE TRADING BLOCKED"):
        TradingLab({"DEMO_A": FakeBroker("A", False), "DEMO_B": FakeBroker("B")})


def test_demo_order_has_stop_take_and_small_risk_size():
    a, b = FakeBroker("A"), FakeBroker("B")
    lab = TradingLab({"DEMO_A": a, "DEMO_B": b})
    exp = lab.submit_demo_trade(lab.agents[0], "TEST", "BUY")
    assert exp.action == "DEMO_ORDER"
    symbol, side, qty, stop, take = a.orders[0]
    assert symbol == "TEST" and side == "BUY"
    assert qty > 0 and stop < 100 < take


def test_problem_solution_journal():
    lab = TradingLab({"DEMO_A": FakeBroker("A"), "DEMO_B": FakeBroker("B")})
    agent = lab.agents[0]
    lab.record_problem(agent, "TEST", "false_breakout", "raise confirmation threshold")
    assert agent.experiences[-1].problem == "false_breakout"
    assert agent.experiences[-1].proposed_solution
