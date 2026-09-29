"""Safe paper/demo trading laboratory for 50 experimental agents.

This module NEVER enables live-money trading. Broker adapters must explicitly
report demo=True. It provides deterministic agent allocation, risk gates,
experience journaling, problem discovery and solution experiments.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Protocol, Iterable
import math

AGENT_COUNT = 50
ACCOUNT_NAMES = ("DEMO_A", "DEMO_B")
STRATEGIES = ("trend", "mean_reversion", "breakout", "momentum", "volatility")


class DemoBroker(Protocol):
    demo: bool
    name: str
    def equity(self) -> float: ...
    def quote(self, symbol: str) -> float: ...
    def place_demo_order(self, symbol: str, side: str, quantity: float, stop_loss: float, take_profit: float) -> str: ...


@dataclass(frozen=True)
class RiskPolicy:
    risk_per_trade: float = 0.0025
    max_daily_loss: float = 0.015
    max_drawdown: float = 0.05
    max_open_positions_per_agent: int = 1
    min_reward_risk: float = 1.5


@dataclass
class Experience:
    timestamp: str
    agent_id: int
    account: str
    symbol: str
    strategy: str
    action: str
    hypothesis: str
    problem: str = ""
    proposed_solution: str = ""
    order_id: str = ""
    pnl: float = 0.0


@dataclass
class TraderAgent:
    agent_id: int
    account: str
    strategy: str
    policy: RiskPolicy = field(default_factory=RiskPolicy)
    experiences: list[Experience] = field(default_factory=list)
    peak_equity: float = 0.0
    daily_pnl: float = 0.0

    def allowed(self, equity: float) -> tuple[bool, str]:
        self.peak_equity = max(self.peak_equity, equity)
        if equity <= 0:
            return False, "invalid_equity"
        if self.daily_pnl <= -(equity * self.policy.max_daily_loss):
            return False, "daily_loss_gate"
        if self.peak_equity and (self.peak_equity - equity) / self.peak_equity >= self.policy.max_drawdown:
            return False, "drawdown_gate"
        return True, "ok"

    def size(self, equity: float, entry: float, stop: float) -> float:
        distance = abs(entry - stop)
        if distance <= 0 or not math.isfinite(distance):
            return 0.0
        return max(0.0, (equity * self.policy.risk_per_trade) / distance)


class TradingLab:
    def __init__(self, brokers: dict[str, DemoBroker]):
        if set(brokers) != set(ACCOUNT_NAMES):
            raise ValueError("Exactly DEMO_A and DEMO_B broker adapters are required")
        if any(not getattr(b, "demo", False) for b in brokers.values()):
            raise RuntimeError("LIVE TRADING BLOCKED: every broker must be demo/paper")
        self.brokers = brokers
        self.agents = [
            TraderAgent(i, ACCOUNT_NAMES[0] if i <= 25 else ACCOUNT_NAMES[1], STRATEGIES[(i-1) % len(STRATEGIES)])
            for i in range(1, AGENT_COUNT + 1)
        ]

    def record_problem(self, agent: TraderAgent, symbol: str, problem: str, solution: str) -> None:
        agent.experiences.append(Experience(
            timestamp=datetime.now(timezone.utc).isoformat(), agent_id=agent.agent_id,
            account=agent.account, symbol=symbol, strategy=agent.strategy,
            action="LEARN", hypothesis="problem-solution iteration",
            problem=problem, proposed_solution=solution,
        ))

    def submit_demo_trade(self, agent: TraderAgent, symbol: str, side: str,
                          stop_pct: float = 0.01, reward_risk: float = 2.0) -> Experience:
        broker = self.brokers[agent.account]
        if not broker.demo:
            raise RuntimeError("LIVE TRADING BLOCKED")
        equity, entry = float(broker.equity()), float(broker.quote(symbol))
        ok, reason = agent.allowed(equity)
        if not ok:
            self.record_problem(agent, symbol, reason, "pause agent; review risk and market regime")
            return agent.experiences[-1]
        rr = max(reward_risk, agent.policy.min_reward_risk)
        stop = entry * (1-stop_pct if side.upper() == "BUY" else 1+stop_pct)
        take = entry + (entry-stop)*rr if side.upper() == "BUY" else entry-(stop-entry)*rr
        qty = agent.size(equity, entry, stop)
        if qty <= 0:
            self.record_problem(agent, symbol, "invalid_position_size", "reject order and validate quote/stop")
            return agent.experiences[-1]
        oid = broker.place_demo_order(symbol, side.upper(), qty, stop, take)
        exp = Experience(datetime.now(timezone.utc).isoformat(), agent.agent_id, agent.account,
                         symbol, agent.strategy, "DEMO_ORDER", f"{agent.strategy} signal", order_id=str(oid))
        agent.experiences.append(exp)
        return exp

    def leaderboard(self) -> list[dict]:
        rows = []
        for a in self.agents:
            pnls = [x.pnl for x in a.experiences if x.action == "DEMO_ORDER"]
            wins = sum(1 for p in pnls if p > 0)
            rows.append({"agent_id": a.agent_id, "account": a.account, "strategy": a.strategy,
                         "trades": len(pnls), "pnl": sum(pnls),
                         "win_rate": wins/len(pnls) if pnls else 0.0,
                         "problems": sum(bool(x.problem) for x in a.experiences)})
        return sorted(rows, key=lambda x: (x["pnl"], x["win_rate"]), reverse=True)

    def snapshot(self) -> dict:
        return {"mode": "DEMO_ONLY", "agents": AGENT_COUNT,
                "allocation": {"DEMO_A": 25, "DEMO_B": 25},
                "leaderboard": self.leaderboard()}
