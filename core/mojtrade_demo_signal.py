"""Single-bot deterministic XAUUSD H1 DEMO setup planner (NO ORDERS).

This pure function uses normalized, explicitly UNAUTHENTICATED broker inputs.
A quote/candle collection is not an authenticated broker fill, and a calculated
price is not an executable order, published signal or trade recommendation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
import hashlib
import json
import re

from core.mojtrade_strategy_risk import assess_account_risk_budget


SCHEMA = "mojtaba.bot.ai.xauusd-h1-demo-input.v1"
OUTPUT_SCHEMA = "mojtaba.bot.ai.private-demo-signal-plan.v1"
CANDLE_INTERVAL = timedelta(hours=1)
MAX_CANDLES = 240
MIN_CANDLES = 60
ALLOWED_PIP_SIZES = frozenset(("0.01", "0.1", "0.001"))
TEXT = {
    "demo_setup_buy": {
        "fa": "طرح آزمایشی خرید طلا؛ سفارش و سیگنال قابل انتشار صادر نشده است.",
        "en": "Provisional gold buy setup; no order or publishable signal issued.",
        "ar": "إعداد شراء تجريبي للذهب؛ لم يصدر أمر أو إشارة قابلة للنشر.",
    },
    "demo_setup_sell": {
        "fa": "طرح آزمایشی فروش طلا؛ سفارش و سیگنال قابل انتشار صادر نشده است.",
        "en": "Provisional gold sell setup; no order or publishable signal issued.",
        "ar": "إعداد بيع تجريبي للذهب؛ لم يصدر أمر أو إشارة قابلة للنشر.",
    },
    "no_setup": {
        "fa": "شرایط تأیید دوگانه فراهم نشده؛ بدون اقدام معاملاتی.",
        "en": "Dual-confirmation setup not found; no trading action.",
        "ar": "لم تتوفر شروط التأكيد المزدوج؛ لا إجراء تداول.",
    },
    "blocked": {
        "fa": "کنترل محدودیت بازار یا ریسک مانع تشکیل طرح شده است.",
        "en": "Market or risk gate blocked this provisional setup.",
        "ar": "منع فحص السوق أو المخاطر هذا الإعداد التجريبي.",
    },
}


class DemoSignalPlanError(ValueError):
    """Reject unsafe, synthetic-looking or stale inputs before pricing."""


def _decimal(value, label: str, *, positive=False, nonnegative=False) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9]\d{0,11})(?:\.\d{1,8})?", value):
        raise DemoSignalPlanError(label + "_invalid_decimal")
    try:
        val = Decimal(value)
    except InvalidOperation as exc:
        raise DemoSignalPlanError(label + "_invalid_decimal") from exc
    if not val.is_finite() or (positive and val <= 0) or (nonnegative and val < 0):
        raise DemoSignalPlanError(label + "_range_invalid")
    return val


def _utc(value, label: str) -> datetime:
    if not isinstance(value, str):
        raise DemoSignalPlanError(label + "_timestamp_required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DemoSignalPlanError(label + "_timestamp_invalid") from exc
    if result.tzinfo is None:
        raise DemoSignalPlanError(label + "_timezone_required")
    return result.astimezone(timezone.utc)


def _keys(data, expected, label):
    if not isinstance(data, dict) or set(data) != set(expected):
        raise DemoSignalPlanError(label + "_schema_rejected")


def _ema(values: list[Decimal], period: int) -> list[Decimal]:
    alpha = Decimal(2) / Decimal(period + 1)
    output = []
    previous = values[0]
    for value in values:
        previous = previous + alpha * (value - previous)
        output.append(previous)
    return output


def _rsi(closes: list[Decimal], period=14) -> Decimal:
    changes = [b - a for a, b in zip(closes, closes[1:])]
    avg_gain = sum((max(diff, Decimal(0)) for diff in changes[:period]), Decimal(0)) / period
    avg_loss = sum((max(-diff, Decimal(0)) for diff in changes[:period]), Decimal(0)) / period
    for diff in changes[period:]:
        avg_gain = (avg_gain * (period - 1) + max(diff, Decimal(0))) / period
        avg_loss = (avg_loss * (period - 1) + max(-diff, Decimal(0))) / period
    if avg_loss == 0:
        return Decimal(100) if avg_gain > 0 else Decimal(50)
    return Decimal(100) - Decimal(100) / (Decimal(1) + avg_gain / avg_loss)


def _atr(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal], period=14):
    true_range = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        true_range.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    return _ema(true_range, period)[-1]


def _price_round(value: Decimal, step: Decimal, direction) -> Decimal:
    return (value / step).to_integral_value(rounding=direction) * step


def plan_private_demo_signal(snapshot: dict, *, now: datetime | None = None) -> dict:
    """Produce a signed-content-addressable *preview*, NEVER trade instructions.

    A future broker adapter must independently authenticate the source and
    prove margin/lot-size/pip-value before this could enter any approval lane.
    This function cannot authorize an order even with forged input flags.
    """
    _keys(snapshot, (
        "schema", "owner", "account_mode", "account_alias", "symbol",
        "timeframe", "generated_at", "expires_at", "quote",
        "candles", "account_risk",
    ), "snapshot")
    if (snapshot["schema"] != SCHEMA or snapshot["owner"] != "mojtaba-bot-ai"
            or snapshot["account_mode"] != "demo"
            or snapshot["symbol"] != "XAUUSD" or snapshot["timeframe"] != "H1"
            or not isinstance(snapshot["account_alias"], str)
            or re.fullmatch(r"[A-Za-z0-9_-]{3,40}", snapshot["account_alias"]) is None):
        raise DemoSignalPlanError("single_bot_demo_gold_scope_required")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise DemoSignalPlanError("now_timezone_required")
    current = current.astimezone(timezone.utc)
    generated = _utc(snapshot["generated_at"], "generated")
    expiry = _utc(snapshot["expires_at"], "expiry")
    if not generated <= current < expiry or expiry - generated > timedelta(minutes=2):
        raise DemoSignalPlanError("snapshot_expired_or_future")

    quote = snapshot["quote"]
    _keys(quote, ("bid", "ask", "pip_size", "tick_size", "observed_at"), "quote")
    bid = _decimal(quote["bid"], "bid", positive=True)
    ask = _decimal(quote["ask"], "ask", positive=True)
    pip = _decimal(quote["pip_size"], "pip", positive=True)
    tick = _decimal(quote["tick_size"], "tick", positive=True)
    observed = _utc(quote["observed_at"], "quote")
    if (quote["pip_size"] not in ALLOWED_PIP_SIZES or tick > pip or
            (pip / tick) != (pip / tick).to_integral_value()
            or ask <= bid or (ask - bid) / pip > Decimal("25")
            or observed > current or current - observed > timedelta(seconds=45)
            or observed < generated - timedelta(seconds=45)):
        raise DemoSignalPlanError("quote_spread_tick_or_freshness_invalid")

    rows = snapshot["candles"]
    if not isinstance(rows, list) or not MIN_CANDLES <= len(rows) <= MAX_CANDLES:
        raise DemoSignalPlanError("closed_h1_history_required")
    opens, highs, lows, closes, times = [], [], [], [], []
    for row in rows:
        _keys(row, ("opened_at", "open", "high", "low", "close"), "candle")
        stamp = _utc(row["opened_at"], "candle")
        if stamp.minute or stamp.second or stamp.microsecond:
            raise DemoSignalPlanError("candle_not_h1_aligned")
        values = [_decimal(row[key], "candle_" + key, positive=True)
                  for key in ("open", "high", "low", "close")]
        if not values[2] <= values[0] <= values[1] or not values[2] <= values[3] <= values[1]:
            raise DemoSignalPlanError("ohlc_invariant_failed")
        times.append(stamp)
        opens.append(values[0])
        highs.append(values[1])
        lows.append(values[2])
        closes.append(values[3])
    if (any(b - a != CANDLE_INTERVAL for a, b in zip(times, times[1:]))
            or times[-1] + CANDLE_INTERVAL > current
            or current - (times[-1] + CANDLE_INTERVAL) > timedelta(hours=2)):
        raise DemoSignalPlanError("candle_gap_open_bar_or_stale")

    risk = snapshot["account_risk"]
    _keys(risk, (
        "equity", "realized_daily_pnl", "open_stop_risk", "free_margin",
        "open_positions", "pending_orders",
    ), "risk")
    if (type(risk["open_positions"]) is not int or type(risk["pending_orders"]) is not int
            or not 0 <= risk["open_positions"] <= 500
            or not 0 <= risk["pending_orders"] <= 500):
        raise DemoSignalPlanError("account_exposure_count_invalid")
    equity = _decimal(risk["equity"], "equity", positive=True)
    _decimal(risk["realized_daily_pnl"].lstrip("-") if isinstance(
        risk["realized_daily_pnl"], str) else risk["realized_daily_pnl"], "daily_pnl")
    pnl = risk["realized_daily_pnl"]
    if (not isinstance(pnl, str) or not re.fullmatch(
        r"-?(?:0|[1-9]\d{0,11})(?:\.\d{1,8})?", pnl
    )):
        raise DemoSignalPlanError("daily_pnl_invalid")
    open_risk = _decimal(risk["open_stop_risk"], "open_risk", nonnegative=True)
    free_margin = _decimal(risk["free_margin"], "free_margin", nonnegative=True)
    assessment = assess_account_risk_budget(
        equity=str(equity), realized_daily_pnl=pnl, open_stop_risk=str(open_risk),
    )
    # Match cTrader dual confirmation: EMA8/34 CROSS, 20-candle breakout
    # (not 2 independent trend indicators), RSI guard, ATR14 EMA smoothing.
    fast = _ema(closes, 8)
    slow = _ema(closes, 34)
    rsi = _rsi(closes)
    atr = _atr(highs, lows, closes)
    up = (fast[-2] <= slow[-2] and fast[-1] > slow[-1] and rsi < 75
          and closes[-1] > max(highs[-21:-1]))
    down = (fast[-2] >= slow[-2] and fast[-1] < slow[-1] and rsi > 25
            and closes[-1] < min(lows[-21:-1]))
    classification = "demo_setup_buy" if up else ("demo_setup_sell" if down else "no_setup")
    capacity = Decimal(assessment["advisory_capacity"])
    gate = "research_only_no_broker_attestation"
    levels = None
    if classification != "no_setup":
        if (risk["open_positions"] >= 3 or risk["pending_orders"] != 0
                or free_margin <= 0 or capacity <= 0):
            classification, gate = "blocked", "portfolio_or_margin_gate_blocked"
        else:
            stop_distance = max(atr * Decimal("2"), pip)
            entry = ask if up else bid
            if up:
                stop = _price_round(entry - stop_distance, tick, ROUND_FLOOR)
                take = _price_round(entry + stop_distance * Decimal("1.8"), tick, ROUND_FLOOR)
            else:
                stop = _price_round(entry + stop_distance, tick, ROUND_CEILING)
                take = _price_round(entry - stop_distance * Decimal("1.8"), tick, ROUND_CEILING)
            if stop <= 0 or take <= 0 or stop == entry or take == entry:
                raise DemoSignalPlanError("indicative_protection_levels_invalid")
            levels = {
                "entry_indicative": str(entry),
                "stop_loss_indicative": str(stop),
                "take_profit_indicative": str(take),
                "estimated_atr_price": str(atr.quantize(Decimal("0.000001"))),
                "quote_spread_pips": str((ask - bid) / pip),
                "order_volume": None,
                "prices_are_executable": False,
            }
    canonical_data = json.dumps(snapshot, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_data.encode("utf-8")).hexdigest()
    return {
        "schema": OUTPUT_SCHEMA,
        "owner": "mojtaba-bot-ai",
        "account_alias": snapshot["account_alias"],
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "source_digest_sha256": digest,
        "source_generated_at": generated.isoformat(),
        "expires_at": expiry.isoformat(),
        "last_closed_candle_at": (times[-1] + CANDLE_INTERVAL).isoformat(),
        "classification": classification,
        "copy": TEXT[classification],
        "levels": levels,
        "risk_advisory_capacity_account_currency": assessment["advisory_capacity"],
        "risk_gate": gate,
        "research_only": True,
        "broker_data_independently_authenticated": False,
        "broker_execution_connected": False,
        "publication_authorized": False,
        "trade_execution_authorized": False,
        "order_intent": None,
        "orders": 0,
        "real_revenue_verified": False,
        "setup_parity_with_cbot_not_broker_verified": True,
    }
