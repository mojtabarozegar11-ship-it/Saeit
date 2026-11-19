"""Deterministic, broker-independent execution engine for MOJ PROP simulation.

This module is deliberately side-effect free outside its in-memory state. It
does not connect to a broker, wallet, payment gateway, or market feed.
Authoritative market-data ingestion and licensing remain separate release gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from .simulation_policy import SIMULATION_POLICY


D = Decimal


def _dec(value, name: str) -> Decimal:
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _positive(value, name: str) -> Decimal:
    result = _dec(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative(value, name: str) -> Decimal:
    result = _dec(value, name)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: str
    sequence: int

    def __post_init__(self):
        if not self.symbol or self.bid <= 0 or self.ask <= 0:
            raise ValueError("quote symbol and prices are required")
        if self.ask < self.bid:
            raise ValueError("ask cannot be below bid")
        if self.sequence < 0 or not self.timestamp:
            raise ValueError("quote timestamp and sequence are required")

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    order_type: str = "market"
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None

    def __post_init__(self):
        if not self.order_id or not self.symbol:
            raise ValueError("order_id and symbol are required")
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if self.order_type not in {"market", "limit", "stop"}:
            raise ValueError("order_type must be market, limit, or stop")
        if _positive(self.quantity, "quantity") <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type == "limit" and self.limit_price is None:
            raise ValueError("limit_price is required")
        if self.order_type == "stop" and self.stop_price is None:
            raise ValueError("stop_price is required")
        if self.stop_loss is None:
            raise ValueError("stop_loss is required")
        if self.take_profit is not None:
            _positive(self.take_profit, "take_profit")


@dataclass
class Position:
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Optional[Decimal]
    opened_sequence: int
    current_bid: Decimal
    current_ask: Decimal

    @property
    def open_risk(self) -> Decimal:
        return abs(self.entry_price - self.stop_loss) * self.quantity

    def unrealized(self) -> Decimal:
        exit_price = self.current_bid if self.side == "buy" else self.current_ask
        direction = D("1") if self.side == "buy" else D("-1")
        return (exit_price - self.entry_price) * self.quantity * direction


@dataclass(frozen=True)
class Execution:
    order_id: str
    status: str
    symbol: str
    side: str
    quantity: Decimal
    price: Optional[Decimal]
    reason: str = ""


@dataclass(frozen=True)
class SimulationSnapshot:
    balance: Decimal
    equity: Decimal
    floating_pnl: Decimal
    realized_pnl: Decimal
    daily_loss: Decimal
    total_loss: Decimal
    open_risk: Decimal
    position_count: int
    pending_count: int
    closed_trade_count: int
    blocked: bool


class SimulationEngine:
    """In-memory challenge execution with fail-closed policy limits."""

    def __init__(self, *, starting_balance=None, commission_per_unit=0,
                 slippage_bps=0):
        if SIMULATION_POLICY.account_mode != "simulated":
            raise ValueError("simulation policy must remain simulated")
        if SIMULATION_POLICY.real_orders_enabled:
            raise ValueError("real orders must remain disabled")
        self.starting_balance = _positive(
            SIMULATION_POLICY.starting_balance_usd
            if starting_balance is None else starting_balance,
            "starting_balance",
        )
        self.balance = self.starting_balance
        self.day_open_equity = self.starting_balance
        self.commission_per_unit = _nonnegative(
            commission_per_unit, "commission_per_unit")
        self.slippage_bps = _nonnegative(slippage_bps, "slippage_bps")
        self.positions: Dict[str, Position] = {}
        self.pending: Dict[str, OrderRequest] = {}
        self.closed_trade_count = 0
        self.realized_pnl = D("0")
        self.last_quote_sequence = -1
        self.blocked = False
        self.closed = []

    @property
    def daily_floor(self) -> Decimal:
        return self.day_open_equity * (
            D("1") - D(str(SIMULATION_POLICY.daily_loss_limit_pct)) / 100)

    @property
    def total_floor(self) -> Decimal:
        return self.starting_balance * (
            D("1") - D(str(SIMULATION_POLICY.total_loss_limit_pct)) / 100)

    def _execution_price(self, order: OrderRequest, quote: MarketQuote) -> Decimal:
        raw = quote.ask if order.side == "buy" else quote.bid
        slip = self.slippage_bps / D("10000")
        return raw * (D("1") + slip if order.side == "buy" else D("1") - slip)

    def _risk_at(self, order: OrderRequest, entry: Decimal) -> Decimal:
        stop = _positive(order.stop_loss, "stop_loss")
        if order.side == "buy" and stop >= entry:
            raise ValueError("buy stop_loss must be below entry")
        if order.side == "sell" and stop <= entry:
            raise ValueError("sell stop_loss must be above entry")
        return abs(entry - stop) * order.quantity + (
            self.commission_per_unit * order.quantity)

    def _current_equity(self) -> Decimal:
        return self.balance + sum(
            (position.unrealized() for position in self.positions.values()),
            D("0"),
        )

    def _risk_gate(self, order: OrderRequest, entry: Decimal) -> Optional[str]:
        risk = self._risk_at(order, entry)
        max_single = self.starting_balance * (
            D(str(SIMULATION_POLICY.max_risk_per_trade_pct)) / 100)
        max_open = self.starting_balance * (
            D(str(SIMULATION_POLICY.max_open_risk_pct)) / 100)
        if risk > max_single:
            return "per_trade_risk_limit"
        if risk + sum((p.open_risk for p in self.positions.values()), D("0")) > max_open:
            return "aggregate_open_risk_limit"
        if self._current_equity() - risk <= max(self.daily_floor, self.total_floor):
            return "drawdown_headroom_limit"
        return None

    def submit(self, order: OrderRequest, quote: MarketQuote) -> Execution:
        if self.blocked:
            return Execution(order.order_id, "rejected", order.symbol,
                             order.side, order.quantity, None, "account_blocked")
        if order.order_id in self.positions or order.order_id in self.pending:
            return Execution(order.order_id, "rejected", order.symbol,
                             order.side, order.quantity, None, "duplicate_order_id")
        if order.symbol != quote.symbol:
            return Execution(order.order_id, "rejected", order.symbol,
                             order.side, order.quantity, None, "quote_symbol_mismatch")
        if quote.sequence <= self.last_quote_sequence:
            return Execution(order.order_id, "rejected", order.symbol,
                             order.side, order.quantity, None, "stale_quote")
        self.last_quote_sequence = quote.sequence
        entry = self._execution_price(order, quote)
        if order.order_type == "market":
            reason = self._risk_gate(order, entry)
            if reason:
                return Execution(order.order_id, "rejected", order.symbol,
                                 order.side, order.quantity, None, reason)
            return self._open(order, entry, quote)
        self.pending[order.order_id] = order
        return Execution(order.order_id, "pending", order.symbol,
                         order.side, order.quantity, None, "awaiting_trigger")

    def process_quote(self, quote: MarketQuote) -> List[Execution]:
        if quote.sequence <= self.last_quote_sequence:
            raise ValueError("quote sequence must increase")
        self.last_quote_sequence = quote.sequence
        for position in self.positions.values():
            position.current_bid = quote.bid
            position.current_ask = quote.ask
        executions = []
        for order_id, order in list(self.pending.items()):
            trigger = (
                order.order_type == "limit" and (
                    (order.side == "buy" and quote.ask <= order.limit_price)
                    or (order.side == "sell" and quote.bid >= order.limit_price)
                )
            ) or (
                order.order_type == "stop" and (
                    (order.side == "buy" and quote.ask >= order.stop_price)
                    or (order.side == "sell" and quote.bid <= order.stop_price)
                )
            )
            if trigger:
                entry = self._execution_price(order, quote)
                reason = self._risk_gate(order, entry)
                if reason:
                    executions.append(Execution(order.order_id, "rejected",
                                                order.symbol, order.side,
                                                order.quantity, None, reason))
                else:
                    executions.append(self._open(order, entry, quote))
                self.pending.pop(order_id, None)
        self._enforce_drawdown()
        return executions

    def _open(self, order: OrderRequest, entry: Decimal,
              quote: MarketQuote) -> Execution:
        self.positions[order.order_id] = Position(
            order_id=order.order_id, symbol=order.symbol, side=order.side,
            quantity=order.quantity, entry_price=entry,
            stop_loss=_positive(order.stop_loss, "stop_loss"),
            take_profit=order.take_profit, opened_sequence=quote.sequence,
            current_bid=quote.bid, current_ask=quote.ask,
        )
        return Execution(order.order_id, "filled", order.symbol, order.side,
                         order.quantity, entry)

    def close(self, order_id: str, quote: MarketQuote,
              reason="manual") -> Execution:
        position = self.positions.get(order_id)
        if position is None:
            raise KeyError(order_id)
        if quote.symbol != position.symbol or quote.sequence <= self.last_quote_sequence:
            raise ValueError("invalid or stale close quote")
        self.last_quote_sequence = quote.sequence
        exit_price = quote.bid if position.side == "buy" else quote.ask
        direction = D("1") if position.side == "buy" else D("-1")
        gross = (exit_price - position.entry_price) * position.quantity * direction
        fees = self.commission_per_unit * position.quantity
        net = gross - fees
        self.balance += net
        self.realized_pnl += net
        self.closed_trade_count += 1
        self.closed.append((order_id, net, reason))
        self.positions.pop(order_id)
        self._enforce_drawdown()
        return Execution(order_id, "closed", position.symbol, position.side,
                         position.quantity, exit_price, reason)

    def _enforce_drawdown(self):
        equity = self._current_equity()
        if equity <= max(self.daily_floor, self.total_floor):
            self.blocked = True

    def snapshot(self) -> SimulationSnapshot:
        floating = self._current_equity() - self.balance
        equity = self.balance + floating
        return SimulationSnapshot(
            balance=self.balance, equity=equity, floating_pnl=floating,
            realized_pnl=self.realized_pnl,
            daily_loss=max(D("0"), self.day_open_equity - equity),
            total_loss=max(D("0"), self.starting_balance - equity),
            open_risk=sum((p.open_risk for p in self.positions.values()), D("0")),
            position_count=len(self.positions), pending_count=len(self.pending),
            closed_trade_count=self.closed_trade_count, blocked=self.blocked,
        )
