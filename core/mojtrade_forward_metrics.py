"""Bounded, offline ONE-hour research reference-close performance model.

A modeled return is neither verified trade P&L nor independently authenticated
exchange evidence. This module never fetches prices or executes an order.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

MAX_HISTORY = 128
MAX_LOOKBACK_DAYS = 45
MIN_MODEL_SAMPLES = 30
HORIZON = timedelta(hours=1)
FEE_BPS_PER_SIDE = Decimal("10")
SLIPPAGE_BPS_PER_SIDE = Decimal("5")
ROUND_TRIP_COST_PCT = (FEE_BPS_PER_SIDE + SLIPPAGE_BPS_PER_SIDE) * 2 / 100
VALID_SOURCES = frozenset((
    "coinbase-exchange-public-candles", "bitstamp-public-ohlc",
    "kraken-spot-public-ohlc", "bitfinex-public-candles",
))
VALID_STANCES = frozenset(("watch_buy", "watch_sell", "neutral"))
SYMBOLS = ("BTC/USD", "ETH/USD")
HASH = re.compile(r"[0-9a-f]{64}\Z")


class ForwardEvidenceError(ValueError):
    """Reject forged, duplicated, out-of-order or unproven model inputs."""


def _time(raw, name):
    if not isinstance(raw, str):
        raise ForwardEvidenceError(name + "_missing")
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ForwardEvidenceError(name + "_invalid") from exc
    if value.tzinfo is None:
        raise ForwardEvidenceError(name + "_naive")
    return value.astimezone(timezone.utc)


def _close_usd(raw):
    if type(raw) not in (float, int):
        raise ForwardEvidenceError("MODEL_USD_CLOSE_INVALID")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise ForwardEvidenceError("MODEL_USD_CLOSE_INVALID") from exc
    if not value.is_finite() or not Decimal(0) < value <= Decimal("1000000000"):
        raise ForwardEvidenceError("MODEL_USD_CLOSE_INVALID")
    return value


def _parse_snapshot(row, now):
    if not isinstance(row, dict) or set(row) != {"reviewed_at", "review"}:
        raise ForwardEvidenceError("MODEL_HISTORY_ROW_INVALID")
    reviewed_at = _time(row["reviewed_at"], "MODEL_REVIEWED_AT")
    report = row["review"]
    if not isinstance(report, dict) or report.get("schema") != "mojtaba.bot.ai.private-market-research-review.v1":
        raise ForwardEvidenceError("MODEL_REVIEW_SCHEMA_INVALID")
    if report.get("canonical_agent") != "economic-master-agent":
        raise ForwardEvidenceError("MODEL_AGENT_MISMATCH")
    controls = report.get("controls")
    if not isinstance(controls, dict) or any(controls.get(k) is not v for k, v in {
        "research_only": True, "orders": 0, "execution": "disabled",
        "publication_enabled": False, "delivery_enabled": False,
        "financial_actions_enabled": False,
    }.items()):
        raise ForwardEvidenceError("MODEL_EXECUTION_BOUNDARY_INVALID")
    sha = report.get("source_sha256")
    if not isinstance(sha, str) or not HASH.fullmatch(sha):
        raise ForwardEvidenceError("MODEL_SOURCE_HASH_INVALID")
    if type(report.get("source_bytes")) is not int or not 0 < report["source_bytes"] <= 96000:
        raise ForwardEvidenceError("MODEL_SOURCE_BYTES_INVALID")
    generated = _time(report.get("observation_generated_at"), "MODEL_GENERATED_AT")
    expires = _time(report.get("observation_expires_at"), "MODEL_EXPIRES_AT")
    if (not generated <= reviewed_at < expires or expires - generated > timedelta(minutes=90)
            or reviewed_at > now or generated > now):
        raise ForwardEvidenceError("MODEL_SOURCE_TIME_INVALID")
    metric = report.get("measurement")
    if not isinstance(metric, dict) or metric.get("verified_observation_count") != 2:
        raise ForwardEvidenceError("MODEL_MEASUREMENT_INVALID")
    observations = report.get("observations")
    if not isinstance(observations, list) or len(observations) != 2:
        raise ForwardEvidenceError("MODEL_OBSERVATION_COUNT_INVALID")
    parsed = []
    missing_price = False
    for symbol, entry in zip(SYMBOLS, observations):
        if not isinstance(entry, dict) or entry.get("symbol") != symbol:
            raise ForwardEvidenceError("MODEL_SYMBOL_ORDER_INVALID")
        if entry.get("stance") not in VALID_STANCES:
            raise ForwardEvidenceError("MODEL_STANCE_INVALID")
        if entry.get("data_source") not in VALID_SOURCES:
            raise ForwardEvidenceError("MODEL_USD_PROVIDER_INVALID")
        if any(not isinstance(entry.get(k), str) or not entry[k].strip()
               for k in ("signal_id", "method")):
            raise ForwardEvidenceError("MODEL_IDENTITY_INVALID")
        observed = _time(entry.get("observed_at"), "MODEL_CANDLE_AT")
        if (observed > generated or generated - observed > timedelta(hours=3)
                or observed.minute or observed.second or observed.microsecond):
            raise ForwardEvidenceError("MODEL_CANDLE_TIME_INVALID")
        if "reference_close_usd" not in entry:
            missing_price = True
            continue
        parsed.append({
            "symbol": symbol, "stance": entry["stance"], "observed": observed,
            "reviewed_at": reviewed_at, "close": _close_usd(entry["reference_close_usd"]),
            "signal_id": entry["signal_id"], "provider": entry["data_source"],
            "source_sha256": sha,
        })
    # Do not mix one legacy missing price with one new observed price.
    return sha, ([] if missing_price else parsed), missing_price


def assess_reviewed_history(history, now=None):
    """Estimate transparent hypothetical one-hour gross/net directional returns.

    history consists only of timestamped, completed reviews retrieved by the
    existing economic master task gateway, never from user-provided prices.
    """
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ForwardEvidenceError("MODEL_HISTORY_LIMIT_INVALID")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ForwardEvidenceError("MODEL_CLOCK_NAIVE")
    now = now.astimezone(timezone.utc)
    seen_source = set()
    seen_candle = {}
    legacy = 0
    duplicate_snapshots = 0
    for row in sorted(history, key=lambda x: x.get("reviewed_at", "") if isinstance(x, dict) else ""):
        sha, signals, missing = _parse_snapshot(row, now)
        if sha in seen_source:
            duplicate_snapshots += 1
            continue
        seen_source.add(sha)
        if missing:
            legacy += 1
            continue
        for signal in signals:
            if signal["observed"] < now - timedelta(days=MAX_LOOKBACK_DAYS):
                continue
            key = (signal["symbol"], signal["observed"])
            # Earliest archived, time-ordered review wins; no choosing the
            # later most profitable price if two sources cover one candle.
            if key not in seen_candle:
                seen_candle[key] = signal

    samples = []
    for (symbol, at), signal in sorted(seen_candle.items()):
        if signal["stance"] == "neutral":
            continue
        other = seen_candle.get((symbol, at + HORIZON))
        if other is None or other["reviewed_at"] <= signal["reviewed_at"]:
            continue
        if signal["reviewed_at"] >= other["observed"]:
            # An alleged entry reviewed after its 'future' close is hindsight.
            continue
        change = (other["close"] - signal["close"]) * Decimal(100) / signal["close"]
        gross = change if signal["stance"] == "watch_buy" else -change
        net = gross - ROUND_TRIP_COST_PCT
        samples.append({
            "symbol": symbol, "stance": signal["stance"],
            "entry_candle_at": at.isoformat(),
            "outcome_candle_at": other["observed"].isoformat(),
            "entry_signal_id": signal["signal_id"],
            "entry_source_sha256": signal["source_sha256"],
            "outcome_source_sha256": other["source_sha256"],
            "entry_provider": signal["provider"], "outcome_provider": other["provider"],
            "gross_reference_return_pct": str(gross.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)),
            "modeled_net_return_pct": str(net.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)),
            "modeled_positive_after_cost": net > 0,
        })
    count = len(samples)
    wins = sum(row["modeled_positive_after_cost"] for row in samples)
    ratio = Decimal(wins) * 100 / count if count >= MIN_MODEL_SAMPLES else None
    mean = sum((Decimal(row["modeled_net_return_pct"]) for row in samples), Decimal(0)) / count if count >= MIN_MODEL_SAMPLES else None
    return {
        "schema": "mojtaba.bot.ai.forward-research-model.v1",
        "canonical_agent": "economic-master-agent",
        "horizon_hours": 1,
        "model": {
            "fee_bps_per_side": int(FEE_BPS_PER_SIDE),
            "slippage_bps_per_side": int(SLIPPAGE_BPS_PER_SIDE),
            "round_trip_cost_pct": str(ROUND_TRIP_COST_PCT),
            "entry_exit": "consecutive_closed_bar_reference_only_no_fills",
        },
        "review_snapshots_seen": len(seen_source),
        "repeated_source_snapshots_ignored": duplicate_snapshots,
        "legacy_snapshots_without_usd_close": legacy,
        "eligible_hypothetical_one_hour_pairs": count,
        "modeled_positive_pairs": wins,
        "minimum_samples_for_modeled_win_rate": MIN_MODEL_SAMPLES,
        "modeled_win_rate_pct": str(ratio.quantize(Decimal("0.01"))) if ratio is not None else None,
        "modeled_mean_net_return_pct": str(mean.quantize(Decimal("0.0001"))) if mean is not None else None,
        "recent_reference_samples": samples[-20:],
        "independently_attested_market_data": False,
        "verified_trade_pnl": None,
        "verified_win_rate": None,
        "collected_revenue": None,
        "research_only": True,
        "execution": "disabled",
        "orders": 0,
        "publication_enabled": False,
    }
