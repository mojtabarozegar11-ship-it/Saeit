#!/usr/bin/env python3
"""Consume a private MojTrade observation as research evidence only.

This module never places orders, contacts a broker, sends email, or changes
the source observation. It refuses expired, malformed, or untrusted payloads.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_SYMBOLS = ("BTC/USD", "ETH/USD")
ALLOWED_STANCES = frozenset({"watch_buy", "watch_sell", "neutral"})
# USD-quoted spot markets only. Binance BTCUSDT/ETHUSDT cannot be
# relabelled as BTC/USD or ETH/USD without breaking price provenance.
ALLOWED_SOURCES = frozenset({
    "coinbase-exchange-public-candles",
    "bitstamp-public-ohlc",
    "kraken-spot-public-ohlc",
    "bitfinex-public-candles",
})


class ObservationError(ValueError):
    """Raised when research evidence cannot be trusted."""


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ObservationError(f"{field}_missing_or_invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ObservationError(f"{field}_invalid") from exc
    if parsed.tzinfo is None:
        raise ObservationError(f"{field}_must_be_timezone_aware")
    return parsed.astimezone(timezone.utc)


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationError(f"{field}_missing_or_invalid")
    return value.strip()


def read_observation(path: Path, now: datetime | None = None) -> dict:
    if not path.is_absolute() or path.is_symlink():
        raise ObservationError("observation_path_must_be_private_absolute_file")
    if not path.is_file():
        raise ObservationError("observation_file_missing")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ObservationError("observation_file_permissions_too_open")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationError("observation_json_unreadable") from exc
    if not isinstance(payload, dict):
        raise ObservationError("observation_payload_not_object")
    if payload.get("schema_version") != 1 or payload.get("source") != "mojtrade-vps":
        raise ObservationError("observation_schema_or_source_rejected")
    generated_at = _timestamp(payload.get("generated_at"), "generated_at")
    expires_at = _timestamp(payload.get("expires_at"), "expires_at")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if expires_at <= now or generated_at > now:
        raise ObservationError("observation_expired_or_future")
    if expires_at <= generated_at:
        raise ObservationError("observation_expiry_window_invalid")
    signals = payload.get("signals")
    if not isinstance(signals, list) or len(signals) != len(EXPECTED_SYMBOLS):
        raise ObservationError("observation_signal_count_invalid")
    normalized = []
    for signal, expected_symbol in zip(signals, EXPECTED_SYMBOLS):
        if not isinstance(signal, dict):
            raise ObservationError("observation_signal_invalid")
        if signal.get("symbol") != expected_symbol:
            raise ObservationError("observation_symbol_order_invalid")
        if signal.get("market") != "crypto" or signal.get("timeframe") != "1h":
            raise ObservationError("observation_market_metadata_invalid")
        stance = signal.get("stance")
        if stance not in ALLOWED_STANCES:
            raise ObservationError("observation_stance_invalid")
        source = signal.get("data_source")
        if source not in ALLOWED_SOURCES:
            raise ObservationError("observation_provider_invalid")
        observed_at = _timestamp(signal.get("observed_at"), "observed_at")
        if observed_at > now or observed_at > expires_at:
            raise ObservationError("observation_signal_time_invalid")
        item = {
            "id": _required_text(signal.get("id"), "signal_id"),
            "symbol": expected_symbol,
            "stance": stance,
            "observed_at": observed_at.isoformat(),
            "data_source": source,
            "method": _required_text(signal.get("method"), "signal_method"),
        }
        # Historical files may lack a reference close; never invent one.
        # A present value must represent a finite positive USD spot close.
        if "reference_close_usd" in signal:
            price = signal["reference_close_usd"]
            if (type(price) not in (float, int)
                    or not math.isfinite(price)
                    or not 0 < price <= 1_000_000_000):
                raise ObservationError("observation_close_usd_invalid")
            item["reference_close_usd"] = float(price)
        normalized.append(item)
    return {
        "schema_version": 1,
        "report_type": "mojtrade-research-observation-consumption",
        "generated_at": now.replace(microsecond=0).isoformat(),
        "observation_generated_at": generated_at.isoformat(),
        "observation_expires_at": expires_at.isoformat(),
        "signals": normalized,
        "execution": "disabled",
        "orders": 0,
        "action": "research_only",
    }


def write_private(report: dict, destination: Path) -> None:
    if not destination.is_absolute() or destination.is_symlink():
        raise ValueError("report_destination_must_be_private_absolute_file")
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise ValueError("report_directory_must_be_private_0700")
    data = (json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".mojtrade-report-", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Consume MojTrade evidence without trading")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = read_observation(args.input)
        write_private(report, args.output)
    except (ObservationError, OSError, ValueError) as exc:
        parser.exit(2, f"MOJTRADE_CONSUMPTION_REJECTED: {exc}\n")
    print("MOJTRADE_RESEARCH_REPORT_WRITTEN: orders=0; execution=disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
