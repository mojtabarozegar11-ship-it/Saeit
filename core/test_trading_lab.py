import json
from datetime import datetime, timezone

import pytest

from core.trading_lab import RiskPolicy, TradingLab


class FakeBroker:
    def __init__(self, name, demo=True, equity=10000.0, quote=100.0):
        self.name, self.demo = name, demo
        self._equity, self._quote = equity, quote
        self.orders = []

    def equity(self):
        return self._equity

    def quote(self, symbol):
        return self._quote

    def place_demo_order(self, symbol, side, quantity, stop_loss, take_profit):
        self.orders.append((symbol, side, quantity, stop_loss, take_profit))
        return f"demo-{len(self.orders)}"


def make_lab(**kwargs):
    return TradingLab({
        "DEMO_A": FakeBroker("A", **kwargs),
        "DEMO_B": FakeBroker("B"),
    })


def test_creates_50_agents_split_across_two_demo_accounts():
    lab = make_lab()
    assert len(lab.agents) == 50
    assert sum(a.account == "DEMO_A" for a in lab.agents) == 25
    assert sum(a.account == "DEMO_B" for a in lab.agents) == 25


def test_live_adapter_is_blocked():
    with pytest.raises(RuntimeError, match="LIVE TRADING BLOCKED"):
        TradingLab({"DEMO_A": FakeBroker("A", demo=False), "DEMO_B": FakeBroker("B")})


def test_demo_order_has_stop_take_and_small_risk_size():
    broker = FakeBroker("A")
    lab = TradingLab({"DEMO_A": broker, "DEMO_B": FakeBroker("B")})
    exp = lab.submit_demo_trade(lab.agents[0], "TEST", "BUY")
    assert exp.action == "DEMO_ORDER"
    symbol, side, qty, stop, take = broker.orders[0]
    assert symbol == "TEST" and side == "BUY"
    assert qty > 0 and stop < 100 < take


def test_open_position_limit_and_close_updates_pnl():
    lab = make_lab()
    agent = lab.agents[0]
    first = lab.submit_demo_trade(agent, "TEST", "BUY")
    blocked = lab.submit_demo_trade(agent, "TEST", "BUY")
    assert blocked.action == "LEARN"
    assert blocked.problem == "open_position_limit"
    closed = lab.close_demo_trade(agent, first.order_id, 12.5,
                                  datetime(2026, 11, 6, 14, tzinfo=timezone.utc))
    assert closed.action == "DEMO_CLOSE"
    assert agent.daily_pnl_by_date["2026-11-06"] == 12.5
    assert lab.leaderboard()[0]["trades"] == 1
    assert lab.leaderboard()[0]["pnl"] == 12.5


def test_rejects_invalid_close_without_mutating_open_state():
    lab = make_lab()
    agent = lab.agents[0]
    opened = lab.submit_demo_trade(agent, "TEST", "BUY")
    with pytest.raises(ValueError, match="pnl_must_be_finite"):
        lab.close_demo_trade(agent, opened.order_id, float("nan"))
    assert agent.open_order_ids == [opened.order_id]
    assert not [item for item in agent.experiences if item.action == "DEMO_CLOSE"]


def test_rejects_invalid_risk_policy():
    with pytest.raises(ValueError, match="risk_ratios"):
        RiskPolicy(risk_per_trade=float("nan"))
    with pytest.raises(ValueError, match="max_open_positions"):
        RiskPolicy(max_open_positions_per_agent=0)
    with pytest.raises(ValueError, match="min_reward_risk"):
        RiskPolicy(min_reward_risk=0)


def test_rejects_invalid_order_inputs():
    lab = make_lab()
    agent = lab.agents[0]
    with pytest.raises(ValueError, match="side_must_be_buy_or_sell"):
        lab.submit_demo_trade(agent, "TEST", "HOLD")
    with pytest.raises(ValueError, match="stop_pct_out_of_range"):
        lab.submit_demo_trade(agent, "TEST", "BUY", stop_pct=0)
    with pytest.raises(ValueError, match="invalid_equity"):
        bad_lab = TradingLab({"DEMO_A": FakeBroker("A", equity=float("nan")), "DEMO_B": FakeBroker("B")})
        bad_lab.submit_demo_trade(bad_lab.agents[0], "TEST", "BUY")


def test_problem_solution_journal_and_durable_export_shape():
    lab = make_lab()
    agent = lab.agents[0]
    lab.record_problem(agent, "TEST", "false_breakout", "raise confirmation threshold")
    exported = lab.export_state()
    json.dumps(exported)
    assert exported["mode"] == "DEMO_ONLY"
    assert exported["agents"][0]["experiences"][0]["action"] == "LEARN"

def test_state_round_trip_and_atomic_tamper_rejection():
    lab = make_lab()
    agent = lab.agents[0]
    opened = lab.submit_demo_trade(agent, "TEST", "BUY")
    state_with_open_order = lab.export_state()

    restored = make_lab()
    restored.restore_state(state_with_open_order)
    assert restored.export_state() == state_with_open_order

    tampered = json.loads(json.dumps(state_with_open_order))
    tampered["agents"][0]["open_order_ids"] = ["ghost-order"]
    before = restored.export_state()
    with pytest.raises(ValueError, match="state_open_order_reconciliation_invalid"):
        restored.restore_state(tampered)
    assert restored.export_state() == before

    restored.close_demo_trade(
        restored.agents[0],
        opened.order_id,
        7.5,
        datetime(2026, 11, 6, 14, tzinfo=timezone.utc),
    )
    closed_state = restored.export_state()
    closed_round_trip = make_lab()
    closed_round_trip.restore_state(closed_state)
    assert closed_round_trip.export_state() == closed_state
    assert closed_round_trip.leaderboard()[0]["pnl"] == 7.5
