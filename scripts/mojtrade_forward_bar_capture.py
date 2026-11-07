#!/usr/bin/env python3
"""Prospective, no-order hourly OHLCV capture using the merged market observer.

Only the latest *closed* bar is stored at its actual local receipt time.
Historical bars are never backdated. No inferred spread or trading permission.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mojtrade_observe_market as observer


SCHEMA = "mojtrade.forward-bar-evidence.v1"
MAX_BYTES = 2_000_000
MAX_RECORDS = 5000
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
OBSERVATION_KEYS = {"schema", "symbol", "venue_claim", "bar_open_utc", "bar_close_utc",
                    "first_observed_at_utc", "open", "high", "low", "close", "volume",
                    "spread_bps", "provenance_authenticated", "research_dataset_eligible",
                    "execution", "publication", "real_orders"}
VENUES = (
    (observer.SOURCE, observer._fetch_candles),
    (observer.BITSTAMP_SOURCE, observer._fetch_bitstamp_candles),
    (observer.BINANCE_SOURCE, observer._fetch_binance_candles),
    (observer.KRAKEN_SOURCE, observer._fetch_kraken_candles),
    (observer.BITFINEX_SOURCE, observer._fetch_bitfinex_candles),
)


class CaptureReject(ValueError):
    """A data-capture event is unsafe or not genuinely prospective."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _utc(clock):
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise CaptureReject("timezone_aware_capture_clock_required")
    return clock.astimezone(timezone.utc)


def _parse_utc(value):
    if not isinstance(value, str) or len(value) > 40:
        raise CaptureReject("timestamp_schema_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaptureReject("timestamp_parse_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise CaptureReject("explicit_utc_timestamp_required")
    return parsed.astimezone(timezone.utc)


def validate_observation(value):
    if (not isinstance(value, dict) or set(value) != OBSERVATION_KEYS
            or value["schema"] != SCHEMA or value["symbol"] not in ("BTC/USD", "ETH/USD")
            or type(value["venue_claim"]) is not str
            or value["venue_claim"] not in {label for label, _ in VENUES}
            or value["spread_bps"] is not None
            or value["provenance_authenticated"] is not False
            or value["research_dataset_eligible"] is not False
            or value["execution"] != "disabled" or value["publication"] != "disabled"
            or type(value["real_orders"]) is not int or value["real_orders"] != 0):
        raise CaptureReject("observation_schema_or_safety_invalid")
    opening = _parse_utc(value["bar_open_utc"])
    closing = _parse_utc(value["bar_close_utc"])
    observed = _parse_utc(value["first_observed_at_utc"])
    if (opening.microsecond or int(opening.timestamp()) % 3600
            or closing - opening != timedelta(hours=1)
            or not closing <= observed < closing + timedelta(hours=1)):
        raise CaptureReject("observation_receipt_or_hour_invalid")
    prices = [value[key] for key in ("open", "high", "low", "close", "volume")]
    if (any(type(n) not in (int, float) or not math.isfinite(n) for n in prices)
            or min(prices[:4]) <= 0 or prices[-1] < 0
            or not value["low"] <= value["open"] <= value["high"]
            or not value["low"] <= value["close"] <= value["high"]):
        raise CaptureReject("observation_ohlcv_invalid")
    return value


def latest_capture(symbol, rows, venue, *, received_at=None):
    """Use the receipt timestamp *after* fetching a real public OHLCV response.

    `received_at` is injectable exclusively for deterministic offline tests; the
    production CLI deliberately offers no timestamp override.
    """
    now = _utc(received_at if received_at is not None else datetime.now(timezone.utc))
    if symbol not in observer.PRODUCTS or venue not in {source for source, _ in VENUES}:
        raise CaptureReject("symbol_or_source_not_supported")
    try:
        _, last_close = observer._validated_closes(rows, now)
    except observer.MarketDataError as exc:
        raise CaptureReject("observer_validation:" + str(exc)) from exc
    delay = (now - last_close).total_seconds()
    if not 0 <= delay < 3600:
        raise CaptureReject("first_capture_too_late_for_current_closed_hour")
    opening = int(last_close.timestamp()) - 3600
    selected = [r for r in rows if type(r) is list and len(r) == 6 and r[0] == opening]
    if len(selected) != 1:
        raise CaptureReject("latest_closed_bar_missing")
    row = selected[0]
    low, high, opened, closed, volume = (float(v) for v in row[1:])
    if (not all(math.isfinite(v) for v in (low, high, opened, closed, volume))
            or low <= 0 or volume < 0 or not low <= opened <= high
            or not low <= closed <= high):
        raise CaptureReject("latest_closed_bar_invalid")
    return {
        "schema": SCHEMA,
        "symbol": symbol.replace("-", "/"),
        "venue_claim": venue,
        "bar_open_utc": datetime.fromtimestamp(opening, tz=timezone.utc).isoformat(),
        "bar_close_utc": last_close.isoformat(),
        "first_observed_at_utc": now.isoformat(),
        "open": opened, "high": high, "low": low, "close": closed,
        "volume": volume,
        "spread_bps": None,
        "provenance_authenticated": False,
        "research_dataset_eligible": False,
        "execution": "disabled",
        "publication": "disabled",
        "real_orders": 0,
    }


def capture_public_once(symbol, *, venues=None, clock=None):
    """Reuse the *existing* observer provider parsers; never call an order API."""
    providers = VENUES if venues is None else venues
    failures = []
    for label, fetcher in providers:
        try:
            rows = fetcher(symbol)
            # Always observe the clock only after this source's fetch returns.
            now = clock() if clock is not None else datetime.now(timezone.utc)
            return latest_capture(symbol, rows, label, received_at=now)
        except (observer.MarketDataError, CaptureReject) as exc:
            failures.append(label + ":" + type(exc).__name__)
    raise CaptureReject("no_valid_public_capture:" + ",".join(failures))


def _read_rows(raw):
    if raw and not raw.endswith(b"\n"):
        raise CaptureReject("journal_partial_write")
    events, prev = [], "0" * 64
    if len(raw) > MAX_BYTES:
        raise CaptureReject("journal_too_large")
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise CaptureReject("journal_json_invalid") from exc
        if (not isinstance(entry, dict) or set(entry) !=
                {"sequence", "previous_sha256", "observation", "entry_sha256"}
                or type(entry["sequence"]) is not int or entry["sequence"] != len(events) + 1
                or entry["previous_sha256"] != prev
                or not isinstance(entry["observation"], dict)
                or entry["observation"].get("schema") != SCHEMA
                or sha({k: v for k, v in entry.items() if k != "entry_sha256"})
                != entry["entry_sha256"]):
            raise CaptureReject("journal_hash_chain_or_schema_invalid")
        validate_observation(entry["observation"])
        if events and entry["observation"]["bar_open_utc"] <= events[-1]["observation"]["bar_open_utc"]:
            raise CaptureReject("journal_bar_order_invalid")
        prev = entry["entry_sha256"]
        events.append(entry)
        if len(events) > MAX_RECORDS:
            raise CaptureReject("journal_record_budget_exceeded")
    return events


def append_private(observation, journal):
    path = Path(journal)
    parent = path.parent
    if (not path.is_absolute() or parent.is_symlink() or not parent.is_dir()
            or stat.S_IMODE(parent.stat().st_mode) != 0o700
            or parent.stat().st_uid != os.geteuid() or path.is_symlink()):
        raise CaptureReject("private_0700_owner_directory_required")
    validate_observation(observation)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | O_NOFOLLOW, 0o600)
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600
                or meta.st_size > MAX_BYTES):
            raise CaptureReject("unsafe_private_journal")
        with os.fdopen(fd, "r+b", buffering=0) as file:
            fd = -1
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            raw = file.read(MAX_BYTES + 1)
            events = _read_rows(raw)
            if events:
                previous = events[-1]["observation"]
                if previous["symbol"] != observation["symbol"]:
                    raise CaptureReject("journal_single_symbol_only")
                if previous["bar_open_utc"] == observation["bar_open_utc"]:
                    comparable = ("schema", "symbol", "venue_claim", "bar_open_utc",
                                  "bar_close_utc", "open", "high", "low", "close", "volume")
                    if any(previous.get(k) != observation.get(k) for k in comparable):
                        raise CaptureReject("conflicting_repeated_bar")
                    return {"written": False, "sequence": events[-1]["sequence"],
                            "entry_sha256": events[-1]["entry_sha256"]}
                if previous["bar_open_utc"] > observation["bar_open_utc"]:
                    raise CaptureReject("out_of_order_bar")
            if len(events) >= MAX_RECORDS:
                raise CaptureReject("journal_record_budget_exceeded")
            entry = {"sequence": len(events) + 1,
                     "previous_sha256": events[-1]["entry_sha256"] if events else "0" * 64,
                     "observation": observation}
            entry["entry_sha256"] = sha(entry)
            encoded = (canonical(entry) + "\n").encode()
            if len(raw) + len(encoded) > MAX_BYTES:
                raise CaptureReject("journal_capacity_exceeded")
            file.seek(0, os.SEEK_END)
            if file.write(encoded) != len(encoded):
                raise CaptureReject("journal_partial_append")
            os.fsync(file.fileno())
            return {"written": True, "sequence": entry["sequence"],
                    "entry_sha256": entry["entry_sha256"]}
    finally:
        if fd >= 0:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prospective public hourly OHLCV evidence only")
    parser.add_argument("--symbol", choices=observer.PRODUCTS, required=True)
    parser.add_argument("--private-journal", type=Path, required=True)
    args = parser.parse_args(argv)
    # No custom timestamp, broker, order, publication or spread flags exist.
    result = append_private(capture_public_once(args.symbol), args.private_journal)
    print(canonical({"schema": SCHEMA, "symbol": args.symbol,
                     "research_dataset_eligible": False,
                     "real_orders": 0, "publication": "disabled", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
