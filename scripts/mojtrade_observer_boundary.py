#!/usr/bin/env python3
"""Read-only integrity/compatibility boundary for the existing VPS observer.

The merged observer emits *watch states*, not the historical, timestamped
OHLC/spread evidence required by MojTrade Strategy Foundry. This audit can
confirm consistency of a private watch payload, never market authenticity,
backtest eligibility, broker readiness, publication or trading permission.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCHEMA = "mojtrade.observer-boundary.v1"
OBSERVER_METHOD = "sma20-sma50-momentum10-v1-closed-1h"
PROVIDERS = frozenset({
    "coinbase-exchange-public-candles",
    "bitstamp-public-ohlc",
    "binance-public-klines",
    "kraken-spot-public-ohlc",
    "bitfinex-public-candles",
})
SIGNAL_KEYS = {"id", "market", "symbol", "timeframe", "stance",
               "observed_at", "method", "data_source"}
MAX_INPUT_BYTES = 16_384
MAX_AGE_SECONDS = 3 * 3600
MAX_CLOCK_SKEW_SECONDS = 120
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
PERMANENT_BLOCKERS = [
    "observer_emits_watch_states_not_historical_ohlcv_bars",
    "per_bar_data_available_at_not_recorded",
    "per_bar_observed_spread_bps_not_recorded",
    "transport_or_venue_provenance_not_independently_authenticated",
    "no_owner_trading_or_publication_release",
]


class ObserverReject(ValueError):
    """Evidence is absent, structurally invalid or unsafe to inspect."""


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or not 15 <= len(value) <= 40:
        raise ObserverReject("timestamp_schema_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObserverReject("timestamp_parse_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ObserverReject("explicit_utc_required")
    return parsed.astimezone(timezone.utc)


def _base():
    return {
        "schema": SCHEMA,
        "mode": "READ_ONLY_WATCH_OBSERVER_COMPATIBILITY",
        "engine_input_eligible": False,
        "market_authenticity_verified": False,
        "broker_connected": False,
        "public_signals": 0,
        "real_orders": 0,
        "commercial_ready": False,
        "execution": "disabled",
        "publication": "disabled",
    }


def audit_observer(payload: object, *, now: datetime | None = None) -> dict:
    """Assess a watch feed without treating its price claims as authenticated.

    Caller-provided `now` exists for deterministic tests; CLI uses system UTC.
    Hashes establish payload identity only, not upstream venue authenticity.
    """
    clock = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ObserverReject("aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "generated_at", "expires_at", "source", "signals"
    }:
        raise ObserverReject("observer_top_level_schema_invalid")
    if (type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["source"] != "mojtrade-vps"):
        raise ObserverReject("unsupported_observer_schema_or_source")
    generated = _utc(payload["generated_at"])
    expires = _utc(payload["expires_at"])
    if (generated > clock + timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
            or expires <= clock or expires - generated != timedelta(minutes=90)):
        raise ObserverReject("observer_expired_or_clock_inconsistent")
    signals = payload["signals"]
    if not isinstance(signals, list) or len(signals) != 2:
        raise ObserverReject("expected_two_watch_signals")
    seen_ids = set()
    source_map = {}
    for index, (signal, expected_symbol) in enumerate(zip(signals, ("BTC/USD", "ETH/USD"))):
        if not isinstance(signal, dict) or set(signal) != SIGNAL_KEYS:
            raise ObserverReject(f"watch_signal_{index}_schema_invalid")
        if (signal["symbol"] != expected_symbol or signal["market"] != "crypto"
                or signal["timeframe"] != "1h" or signal["method"] != OBSERVER_METHOD
                or signal["stance"] not in ("watch_buy", "watch_sell", "neutral")
                or signal["data_source"] not in PROVIDERS):
            raise ObserverReject(f"watch_signal_{index}_unsupported_value")
        close_time = _utc(signal["observed_at"])
        if (close_time.microsecond or int(close_time.timestamp()) % 3600
                or close_time > generated
                or (generated - close_time).total_seconds() > MAX_AGE_SECONDS):
            raise ObserverReject(f"watch_signal_{index}_stale_or_unclosed_bar")
        expected_id = hashlib.sha256(
            f"{expected_symbol.replace('/', '-')}|{signal['observed_at']}|"
            f"{OBSERVER_METHOD}|{signal['data_source']}".encode("utf-8")
        ).hexdigest()[:24]
        if signal["id"] != expected_id or expected_id in seen_ids:
            raise ObserverReject(f"watch_signal_{index}_id_mismatch")
        seen_ids.add(expected_id)
        source_map[expected_symbol] = signal["data_source"]
    # This digest is not a signature and does not prove the reported source.
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return {**_base(), "state": "CONSISTENT_WATCH_PAYLOAD_RESEARCH_ONLY",
            "observer_payload_sha256": digest,
            "observed_symbols": ["BTC/USD", "ETH/USD"],
            "claimed_data_sources": source_map,
            "watch_stances_validated": 2,
            "blockers": list(PERMANENT_BLOCKERS)}


def read_private_payload(path: Path) -> object:
    """Read only a caller-owned, private 0600 regular file in a 0700 folder."""
    path = Path(path)
    parent = path.parent
    if (not path.is_absolute() or path.is_symlink() or parent.is_symlink()
            or not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) != 0o700
            or parent.stat().st_uid != os.geteuid()):
        raise ObserverReject("private_absolute_parent_required")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | O_NOFOLLOW)
    except OSError as exc:
        raise ObserverReject("observer_private_file_unavailable") from exc
    try:
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or not 0 < metadata.st_size <= MAX_INPUT_BYTES):
            raise ObserverReject("private_observer_permissions_or_size_invalid")
        with os.fdopen(fd, "rb") as file:
            fd = -1
            fcntl.flock(file.fileno(), fcntl.LOCK_SH)
            data = file.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise ObserverReject("observer_file_too_large")
        try:
            return json.loads(data)
        except (ValueError, UnicodeError) as exc:
            raise ObserverReject("observer_json_invalid") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only MojTrade watch-observer boundary audit")
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_observer(read_private_payload(args.input))
    except (ObserverReject, OSError, TypeError, OverflowError) as exc:
        report = {**_base(), "state": "BLOCKED_OBSERVER_EVIDENCE",
                  "blockers": [type(exc).__name__ + ":" + str(exc)[:100],
                               *PERMANENT_BLOCKERS]}
        print(json.dumps(report, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
