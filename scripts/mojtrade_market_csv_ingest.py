#!/usr/bin/env python3
"""Ingest observed, closed market bars from a local CSV; never fetch quotes.

No timestamp or market value is synthesized. ``available_at_utc`` must be
provided by the data capture, not derived or silently equated to bar close.
Provenance remains UNVERIFIED even when a caller supplies a provider name.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mojtrade_strategy_foundry as foundry


SCHEMA = "mojtrade.market-csv-ingest.v1"
FIELDS = ["bar_open_utc", "available_at_utc", "open", "high", "low", "close", "spread_bps"]
MAX_CSV_BYTES = 950_000


class IngestReject(ValueError):
    """The imported observation is not sufficiently well-formed for research."""


def _utc(value):
    if not isinstance(value, str) or len(value) > 40:
        raise IngestReject("timestamp_invalid")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IngestReject("timestamp_parse") from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise IngestReject("explicit_utc_required")
    return dt.astimezone(timezone.utc)


def import_csv_bytes(raw, *, symbol, interval_seconds, claimed_provider="UNKNOWN"):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_CSV_BYTES:
        raise IngestReject("csv_size_or_type_invalid")
    if (not isinstance(claimed_provider, str) or len(claimed_provider) > 80 or
            any(ord(c) < 32 for c in claimed_provider)):
        raise IngestReject("provider_label_invalid")
    if type(interval_seconds) is not int or interval_seconds not in foundry.ALLOWED_INTERVALS:
        raise IngestReject("interval_invalid")
    try:
        payload = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestReject("csv_not_utf8") from exc
    if "\x00" in payload:
        raise IngestReject("csv_null_bytes")
    reader = csv.DictReader(io.StringIO(payload, newline=""), strict=True)
    if reader.fieldnames != FIELDS:
        raise IngestReject("csv_header_invalid")
    rows = []
    last_open = None
    last_observed = None
    try:
        for item in reader:
            if set(item) != set(FIELDS) or any(item[key] is None or not item[key].strip() for key in FIELDS):
                raise IngestReject("csv_row_schema")
            opening, observed = _utc(item["bar_open_utc"]), _utc(item["available_at_utc"])
            closing = opening + timedelta(seconds=interval_seconds)
            if (last_open is not None and
                    (opening - last_open).total_seconds() != interval_seconds):
                raise IngestReject("bar_gap_duplicate_or_out_of_order")
            if (observed < closing or observed > closing + timedelta(seconds=interval_seconds) or
                    (last_observed is not None and observed <= last_observed)):
                raise IngestReject("bar_observed_before_close_or_out_of_order")
            last_open, last_observed = opening, observed
            def number(key):
                value = item[key]
                if len(value) > 32:
                    raise IngestReject("number_too_long")
                try:
                    return float(value)
                except ValueError as exc:
                    raise IngestReject("number_invalid") from exc
            rows.append({"t": closing.isoformat(), "available_at": observed.isoformat(),
                         "open": number("open"), "high": number("high"),
                         "low": number("low"), "close": number("close"),
                         "spread_bps": number("spread_bps")})
            if len(rows) > foundry.MAX_BARS:
                raise IngestReject("bar_budget_exceeded")
    except csv.Error as exc:
        raise IngestReject("csv_malformed") from exc
    if len(rows) < foundry.MIN_BARS:
        raise IngestReject("insufficient_bars")
    raw_sha = hashlib.sha256(raw).hexdigest()
    source_id = "unverified-csv-" + raw_sha[:24]
    try:
        dataset = foundry.validate_dataset({"source_id": source_id, "symbol": symbol,
                                           "interval_seconds": interval_seconds, "bars": rows})
    except foundry.FoundryError as exc:
        raise IngestReject("foundry_dataset:" + str(exc)) from exc
    manifest = {
        "schema": SCHEMA,
        "evidence_status": "UNVERIFIED_LOCAL_EXPORT",
        "broker_or_venue_authenticated": False,
        "market_data_reality_verified": False,
        "provider_claim_not_evidence": claimed_provider,
        "file_sha256": raw_sha,
        "normalized_dataset_sha256": foundry.digest(dataset),
        "count": len(rows), "symbol": symbol, "interval_seconds": interval_seconds,
        "first_bar_close_at": rows[0]["t"], "last_bar_close_at": rows[-1]["t"],
        "last_observed_at": rows[-1]["available_at"],
        "market_order_permission": False,
        "limitations": ["CSV values and availability timestamps are caller supplied",
                        "hash detects byte changes but does not authenticate a provider",
                        "broker or exchange audit trail and signature are missing",
                        "input quality is not trading profitability proof"],
    }
    return {"dataset": dataset, "manifest": manifest}


def ingest_file(path, **kwargs):
    source = Path(path)
    if source.is_symlink():
        raise IngestReject("regular_file_required")
    try:
        fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise IngestReject("regular_file_required") from exc
    with os.fdopen(fd, "rb") as handle:
        meta = os.fstat(handle.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or
                meta.st_size > MAX_CSV_BYTES):
            raise IngestReject("oversize_or_linked_input")
        raw = handle.read(MAX_CSV_BYTES + 1)
    return import_csv_bytes(raw, **kwargs)


def save_private(result, output):
    path = Path(output)
    parent = path.parent
    if (parent.is_symlink() or not parent.is_dir() or
            stat.S_IMODE(parent.stat().st_mode) != 0o700 or path.is_symlink()):
        raise IngestReject("private_directory_0700_required")
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode() + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb", buffering=0) as handle:
            fd = -1
            if handle.write(encoded) != len(encoded):
                raise IngestReject("output_partial_write")
            os.fsync(handle.fileno())
    finally:
        if fd >= 0:
            os.close(fd)
    return {"path": str(path), "dataset_sha256": result["manifest"]["normalized_dataset_sha256"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline observation-time checked CSV bar importer")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--interval-seconds", required=True, type=int)
    parser.add_argument("--claimed-provider", default="UNKNOWN")
    args = parser.parse_args(argv)
    result = ingest_file(args.input, symbol=args.symbol, interval_seconds=args.interval_seconds,
                         claimed_provider=args.claimed_provider)
    print(json.dumps(save_private(result, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
