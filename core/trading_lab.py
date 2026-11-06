"""Safe paper/demo trading laboratory for 50 experimental agents.

This module NEVER enables live-money trading. Broker adapters must explicitly
report demo=True. Orders are bounded, open-position limits are enforced, and
performance is calculated only from explicitly closed demo trades.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Protocol
import math


AGENT_COUNT = 50
ACCOUNT_NAMES = ("DEMO_A", "DEMO_B")
STRATEGIES = ("trend", "mean_reversion", "breakout", "momentum", "volatility")
ALLOWED_SIDES = frozenset({"BUY", "SELL"})


class DemoBroker(Protocol):
    demo: bool
    name: str

    def equity(self) -> float: ...
    def quote(self, symbol: str) -> float: ...

    def place_demo_order(
        self, symbol: str, side: str, quantity: float, stop_loss: float, take_profit: float
    ) -> str: ...


@dataclass(frozen=True)
class RiskPolicy:
    risk_per_trade: float = 0.0025
    max_daily_loss: float = 0.015
    max_drawdown: float = 0.05
    max_open_positions_per_agent: int = 1
    min_reward_risk: float = 1.5

    def __post_init__(self) -> None:
        ratios = (self.risk_per_trade, self.max_daily_loss, self.max_drawdown)
        if not all(math.isfinite(value) and 0 < value <= 1 for value in ratios):
            raise ValueError("risk_ratios_must_be_finite_between_zero_and_one")
        if type(self.max_open_positions_per_agent) is not int or self.max_open_positions_per_agent < 1:
            raise ValueError("max_open_positions_must_be_positive_integer")
        if not math.isfinite(self.min_reward_risk) or self.min_reward_risk < 1:
            raise ValueError("min_reward_risk_must_be_finite_at_least_one")


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
    open_order_ids: list[str] = field(default_factory=list)
    peak_equity: float = 0.0
    daily_pnl_by_date: dict[str, float] = field(default_factory=dict)

    @property
    def daily_pnl(self) -> float:
        today = datetime.now(timezone.utc).date().isoformat()
        return self.daily_pnl_by_date.get(today, 0.0)

    def allowed(self, equity: float) -> tuple[bool, str]:
        if not math.isfinite(equity) or equity <= 0:
            return False, "invalid_equity"
        self.peak_equity = max(self.peak_equity, equity)
        if self.daily_pnl <= -(equity * self.policy.max_daily_loss):
            return False, "daily_loss_gate"
        if self.peak_equity and (self.peak_equity - equity) / self.peak_equity >= self.policy.max_drawdown:
            return False, "drawdown_gate"
        if len(self.open_order_ids) >= self.policy.max_open_positions_per_agent:
            return False, "open_position_limit"
        return True, "ok"

    def size(self, equity: float, entry: float, stop: float) -> float:
        values = (equity, entry, stop)
        if not all(math.isfinite(value) and value > 0 for value in values):
            return 0.0
        distance = abs(entry - stop)
        if not math.isfinite(distance) or distance <= 0:
            return 0.0
        quantity = (equity * self.policy.risk_per_trade) / distance
        return quantity if math.isfinite(quantity) and quantity > 0 else 0.0

    def record_closed_pnl(self, pnl: float, closed_at: datetime | None = None) -> None:
        if not math.isfinite(pnl):
            raise ValueError("pnl_must_be_finite")
        moment = closed_at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("closed_at_must_be_timezone_aware")
        day = moment.astimezone(timezone.utc).date().isoformat()
        self.daily_pnl_by_date[day] = self.daily_pnl_by_date.get(day, 0.0) + pnl


class TradingLab:
    def __init__(self, brokers: dict[str, DemoBroker]):
        if set(brokers) != set(ACCOUNT_NAMES):
            raise ValueError("Exactly DEMO_A and DEMO_B broker adapters are required")
        if any(not getattr(b, "demo", False) for b in brokers.values()):
            raise RuntimeError("LIVE TRADING BLOCKED: every broker must be demo/paper")
        self.brokers = brokers
        self.agents = [
            TraderAgent(
                i,
                ACCOUNT_NAMES[0] if i <= 25 else ACCOUNT_NAMES[1],
                STRATEGIES[(i - 1) % len(STRATEGIES)],
            )
            for i in range(1, AGENT_COUNT + 1)
        ]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def record_problem(self, agent: TraderAgent, symbol: str, problem: str, solution: str) -> None:
        agent.experiences.append(Experience(
            timestamp=self._now(), agent_id=agent.agent_id, account=agent.account,
            symbol=symbol, strategy=agent.strategy, action="LEARN",
            hypothesis="problem-solution iteration", problem=problem,
            proposed_solution=solution,
        ))

    def submit_demo_trade(
        self, agent: TraderAgent, symbol: str, side: str,
        stop_pct: float = 0.01, reward_risk: float = 2.0,
    ) -> Experience:
        if agent.account not in self.brokers or agent not in self.agents:
            raise ValueError("agent_not_registered")
        side = side.upper() if isinstance(side, str) else ""
        if side not in ALLOWED_SIDES:
            raise ValueError("side_must_be_buy_or_sell")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol_required")
        if not math.isfinite(stop_pct) or not 0 < stop_pct <= 0.5:
            raise ValueError("stop_pct_out_of_range")
        if not math.isfinite(reward_risk) or reward_risk <= 0:
            raise ValueError("reward_risk_invalid")
        broker = self.brokers[agent.account]
        if not broker.demo:
            raise RuntimeError("LIVE TRADING BLOCKED")
        equity, entry = float(broker.equity()), float(broker.quote(symbol.strip()))
        ok, reason = agent.allowed(equity)
        if not ok:
            self.record_problem(agent, symbol.strip(), reason, "pause agent; review risk and market regime")
            return agent.experiences[-1]
        rr = max(reward_risk, agent.policy.min_reward_risk)
        stop = entry * (1 - stop_pct if side == "BUY" else 1 + stop_pct)
        take = entry + (entry - stop) * rr if side == "BUY" else entry - (stop - entry) * rr
        qty = agent.size(equity, entry, stop)
        if qty <= 0 or not all(math.isfinite(value) and value > 0 for value in (stop, take)):
            self.record_problem(agent, symbol.strip(), "invalid_position_size", "reject order and validate quote/stop")
            return agent.experiences[-1]
        oid = broker.place_demo_order(symbol.strip(), side, qty, stop, take)
        if not isinstance(oid, str) or not oid.strip() or oid in agent.open_order_ids:
            raise ValueError("demo_order_id_invalid_or_duplicate")
        agent.open_order_ids.append(oid)
        exp = Experience(
            self._now(), agent.agent_id, agent.account, symbol.strip(), agent.strategy,
            "DEMO_ORDER", f"{agent.strategy} signal", order_id=oid,
        )
        agent.experiences.append(exp)
        return exp

    def close_demo_trade(
        self, agent: TraderAgent, order_id: str, pnl: float,
        closed_at: datetime | None = None,
    ) -> Experience:
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("demo_order_id_required")
        if order_id not in agent.open_order_ids:
            raise ValueError("demo_order_not_open")
        # Validate and account for P&L before mutating the open-position set.
        agent.record_closed_pnl(pnl, closed_at)
        agent.open_order_ids.remove(order_id)
        exp = Experience(
            self._now(), agent.agent_id, agent.account, "", agent.strategy,
            "DEMO_CLOSE", "closed demo trade", order_id=order_id, pnl=pnl,
        )
        agent.experiences.append(exp)
        return exp

    def leaderboard(self) -> list[dict]:
        rows = []
        for agent in self.agents:
            orders = [x for x in agent.experiences if x.action == "DEMO_ORDER"]
            closes = [x for x in agent.experiences if x.action == "DEMO_CLOSE"]
            pnls = [x.pnl for x in closes]
            wins = sum(1 for pnl in pnls if pnl > 0)
            rows.append({
                "agent_id": agent.agent_id, "account": agent.account,
                "strategy": agent.strategy, "orders_submitted": len(orders),
                "trades": len(closes), "open_positions": len(agent.open_order_ids),
                "pnl": sum(pnls), "win_rate": wins / len(pnls) if pnls else 0.0,
                "problems": sum(bool(x.problem) for x in agent.experiences),
            })
        return sorted(rows, key=lambda row: (row["pnl"], row["win_rate"]), reverse=True)

    def snapshot(self) -> dict:
        return {
            "mode": "DEMO_ONLY", "agents": AGENT_COUNT,
            "allocation": {"DEMO_A": 25, "DEMO_B": 25},
            "leaderboard": self.leaderboard(),
        }

    def export_state(self) -> dict:
        """Return JSON-serializable state for an external durable store."""
        return {
            "mode": "DEMO_ONLY",
            "agents": [
                {
                    "agent_id": agent.agent_id, "account": agent.account,
                    "strategy": agent.strategy,
                    "open_order_ids": list(agent.open_order_ids),
                    "peak_equity": agent.peak_equity,
                    "daily_pnl_by_date": dict(agent.daily_pnl_by_date),
                    "experiences": [asdict(item) for item in agent.experiences],
                }
                for agent in self.agents
            ],
        }
