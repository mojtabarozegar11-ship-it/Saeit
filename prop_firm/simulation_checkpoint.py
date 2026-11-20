"""Validated in-memory simulation checkpoint; restored engines are quarantined.

This module is not a live customer execution runner. It cannot authenticate a
quote, trading session, financial reward, or customer account. Its purpose is
to provide a bounded, deterministic state image and safe restart inspection.
"""
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from .simulation_engine import SimulationEngine, OrderRequest, Position, ClosedExecutionRecord
from .simulation_execution_journal import JournalConflict

SCHEMA = "mojprop.simulated.engine.checkpoint.v1"
LIMIT = 10000


def _money(value):
    if type(value) is not Decimal or not value.is_finite():
        raise JournalConflict("finite exact decimal required")
    parts = value.as_tuple()
    if len(parts.digits) > 38 or abs(parts.exponent) > 30:
        raise JournalConflict("decimal exceeds checkpoint bounds")
    return format(value, "f")


def _read_money(value):
    if type(value) is not str or len(value) > 80:
        raise JournalConflict("decimal must be serialized text")
    try:
        number = Decimal(value)
        _money(number)
    except (ValueError, ArithmeticError) as exc:
        raise JournalConflict("invalid checkpoint decimal") from exc
    return number


def _datetime(value):
    if type(value) is not datetime or value.utcoffset() is None:
        raise JournalConflict("timezone-aware datetime required")
    return value.astimezone(timezone.utc).isoformat()


def _read_datetime(value):
    if type(value) is not str or len(value) > 48:
        raise JournalConflict("invalid checkpoint timestamp")
    try:
        v = datetime.fromisoformat(value)
        return datetime.fromisoformat(_datetime(v))
    except (ValueError, TypeError, OverflowError) as exc:
        raise JournalConflict("invalid checkpoint timestamp") from exc


def _text(value, maximum=160):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise JournalConflict("invalid checkpoint text")
    return value


def _order_dict(o):
    return {
        "order_id": _text(o.order_id), "symbol": _text(o.symbol, 64),
        "side": o.side, "quantity": _money(o.quantity),
        "order_type": o.order_type,
        "limit_price": None if o.limit_price is None else _money(o.limit_price),
        "stop_price": None if o.stop_price is None else _money(o.stop_price),
        "stop_loss": _money(o.stop_loss),
        "take_profit": None if o.take_profit is None else _money(o.take_profit),
    }


def _load_order(p):
    if type(p) is not dict or set(p) != {
        "order_id", "symbol", "side", "quantity", "order_type",
        "limit_price", "stop_price", "stop_loss", "take_profit",
    }:
        raise JournalConflict("invalid pending order schema")
    return OrderRequest(
        order_id=_text(p["order_id"]), symbol=_text(p["symbol"], 64),
        side=p["side"], quantity=_read_money(p["quantity"]),
        order_type=p["order_type"],
        limit_price=None if p["limit_price"] is None else _read_money(p["limit_price"]),
        stop_price=None if p["stop_price"] is None else _read_money(p["stop_price"]),
        stop_loss=_read_money(p["stop_loss"]),
        take_profit=None if p["take_profit"] is None else _read_money(p["take_profit"]),
    )


def _position_dict(p):
    return {
        "order_id": _text(p.order_id), "symbol": _text(p.symbol, 64),
        "side": p.side, "quantity": _money(p.quantity),
        "entry_price": _money(p.entry_price), "stop_loss": _money(p.stop_loss),
        "take_profit": None if p.take_profit is None else _money(p.take_profit),
        "opened_sequence": p.opened_sequence, "opened_at": _datetime(p.opened_at),
        "current_bid": _money(p.current_bid), "current_ask": _money(p.current_ask),
    }


def _load_position(p, last_sequence, last_time):
    if type(p) is not dict or set(p) != {
        "order_id", "symbol", "side", "quantity", "entry_price", "stop_loss",
        "take_profit", "opened_sequence", "opened_at", "current_bid", "current_ask",
    }:
        raise JournalConflict("invalid open position schema")
    number = p["opened_sequence"]
    if type(number) is not int or not 0 <= number <= last_sequence:
        raise JournalConflict("invalid position opening sequence")
    opening = _read_datetime(p["opened_at"])
    if last_time is None or opening > last_time:
        raise JournalConflict("position time after last quote")
    side = p["side"]
    qty,entry,stop,bid,ask = (
        _read_money(p["quantity"]),_read_money(p["entry_price"]),
        _read_money(p["stop_loss"]),_read_money(p["current_bid"]),
        _read_money(p["current_ask"]))
    target=None if p["take_profit"] is None else _read_money(p["take_profit"])
    if (side not in ("buy","sell") or min(qty,entry,stop,bid,ask) <= 0 or ask < bid
            or (side=="buy" and not stop < entry)
            or (side=="sell" and not stop > entry)
            or (target is not None and (target<=entry if side=="buy" else target>=entry))):
        raise JournalConflict("invalid position risk or quote state")
    return Position(order_id=_text(p["order_id"]),
        symbol=_text(p["symbol"],64),side=side,quantity=qty,
        entry_price=entry,stop_loss=stop,take_profit=target,
        opened_sequence=number,opened_at=opening,
        current_bid=bid,current_ask=ask)


def export_checkpoint(engine):
    if type(engine) is not SimulationEngine:
        raise JournalConflict("internal simulation engine required")
    if getattr(engine,"quarantined",False):
        raise JournalConflict("quarantined engine cannot be checkpointed")
    if (len(engine.positions)>LIMIT or len(engine.pending)>LIMIT
            or engine.closed_trade_count>LIMIT
            or len(engine.closed_execution_records)!=engine.closed_trade_count):
        raise JournalConflict("engine exceeds checkpoint bounds")
    if type(engine.last_quote_sequence) is not int or engine.last_quote_sequence < -1:
        raise JournalConflict("invalid quote sequence")
    if (engine.last_quote_sequence==-1)!=(engine.last_quote_time is None):
        raise JournalConflict("missing quote sequence or timestamp")
    if type(engine.blocked) is not bool:
        raise JournalConflict("invalid engine risk status")
    state = {
        "schema":SCHEMA, "starting_balance":_money(engine.starting_balance),
        "balance":_money(engine.balance),"day_open_equity":_money(engine.day_open_equity),
        "realized_pnl":_money(engine.realized_pnl),
        "commission_per_unit":_money(engine.commission_per_unit),
        "slippage_bps":_money(engine.slippage_bps),
        "last_quote_sequence":engine.last_quote_sequence,
        "last_quote_time":None if engine.last_quote_time is None else _datetime(engine.last_quote_time),
        "blocked_when_captured":engine.blocked,
        "closed_trade_count":engine.closed_trade_count,
        "positions":[_position_dict(p) for _,p in sorted(engine.positions.items())],
        "pending":[_order_dict(p) for _,p in sorted(engine.pending.items())],
    }
    if (set(engine.positions)&set(engine.pending)
            or any(x["order_id"]!=key for key,x in zip(sorted(engine.positions),state["positions"]))
            or any(x["order_id"]!=key for key,x in zip(sorted(engine.pending),state["pending"]))):
        raise JournalConflict("engine state map key mismatch")
    return state


def recover_quarantined_engine(state, *, closed_records):
    """Restore for restricted inspection only, never resume trading automatically."""
    if type(state) is not dict or set(state) != {
        "schema","starting_balance","balance","day_open_equity","realized_pnl",
        "commission_per_unit","slippage_bps","last_quote_sequence","last_quote_time",
        "blocked_when_captured","closed_trade_count","positions","pending",
    } or state["schema"]!=SCHEMA:
        raise JournalConflict("unsupported checkpoint schema")
    last_seq=state["last_quote_sequence"]
    if type(last_seq) is not int or last_seq < -1:
        raise JournalConflict("invalid last sequence")
    last_time=None if state["last_quote_time"] is None else _read_datetime(state["last_quote_time"])
    if (last_seq==-1)!=(last_time is None):
        raise JournalConflict("last quote sequence/time mismatch")
    if type(state["blocked_when_captured"]) is not bool:
        raise JournalConflict("invalid captured risk state")
    if type(state["closed_trade_count"]) is not int or not 0<=state["closed_trade_count"]<=LIMIT:
        raise JournalConflict("invalid closure count")
    positions,pending=state["positions"],state["pending"]
    if not isinstance(positions,list) or not isinstance(pending,list) or len(positions)>LIMIT or len(pending)>LIMIT:
        raise JournalConflict("position and order bounds exceeded")
    if type(closed_records) not in (tuple,list) or len(closed_records)!=state["closed_trade_count"]:
        raise JournalConflict("journal closure count inconsistent")
    if any(type(r) is not ClosedExecutionRecord for r in closed_records):
        raise JournalConflict("journal closure record invalid")
    starting,balance,day_open,realized=tuple(_read_money(state[k]) for k in (
        "starting_balance","balance","day_open_equity","realized_pnl"))
    if starting <= 0 or day_open<=0 or Fraction(starting)+Fraction(realized)!=balance:
        raise JournalConflict("checkpoint balance reconciliation mismatch")
    if sum((Fraction(r.net_pnl) for r in closed_records),Fraction(0))!=realized:
        raise JournalConflict("journal net P&L mismatch")
    engine=SimulationEngine(starting_balance=starting,
        commission_per_unit=_read_money(state["commission_per_unit"]),
        slippage_bps=_read_money(state["slippage_bps"]))
    engine.balance=balance
    engine.day_open_equity=day_open
    engine.realized_pnl=realized
    engine.last_quote_sequence=last_seq
    engine.last_quote_time=last_time
    for value in positions:
        p=_load_position(value,last_seq,last_time)
        if p.order_id in engine.positions:
            raise JournalConflict("duplicated open position")
        engine.positions[p.order_id]=p
    for value in pending:
        o=_load_order(value)
        if o.order_id in engine.pending or o.order_id in engine.positions:
            raise JournalConflict("duplicated pending order")
        engine.pending[o.order_id]=o
    previous=-1
    closed_ids=set()
    for r in closed_records:
        if r.order_id in closed_ids or r.order_id in engine.positions or r.order_id in engine.pending:
            raise JournalConflict("closure ID conflict")
        if not 0<=r.opened_sequence<r.closed_sequence<=last_seq or r.closed_sequence<previous:
            raise JournalConflict("closure quote sequence mismatch")
        if r.opened_at>r.closed_at or (last_time is not None and r.closed_at>last_time):
            raise JournalConflict("closure time inconsistent")
        closed_ids.add(r.order_id)
        previous=r.closed_sequence
        engine._closed_execution_records.append(r)
        engine.closed.append((r.order_id,r.net_pnl,r.reason))
    engine.closed_trade_count=len(closed_records)
    # Quarantine applies even to an originally unblocked checkpoint.
    # Resuming requires an authenticated feed and explicitly validated account.
    engine.blocked=True
    engine.quarantined=True
    return engine
