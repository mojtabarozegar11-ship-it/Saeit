#!/usr/bin/env python3
"""Promote strictly witnessed local OHLCV+quote history to *research only*.

Consumes the append-only prospective capture journal. Never makes missing bars,
backdates receipt times, blends venues, estimates fees or authorizes orders.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
from datetime import datetime
from pathlib import Path

import mojtrade_forward_bar_capture as capture
import mojtrade_strategy_foundry as foundry


SCHEMA = "mojtrade.forward-dataset-gate.v1"
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class ForwardDatasetReject(ValueError):
    """No complete, coherent forward dataset is available."""


def _private_path(path):
    path = Path(path)
    parent = path.parent
    if (not path.is_absolute() or path.is_symlink() or parent.is_symlink()
            or not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) != 0o700
            or parent.stat().st_uid != os.geteuid()):
        raise ForwardDatasetReject("absolute_owner_private_path_required")
    return path


def read_journal(path):
    source = _private_path(path)
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK | O_NOFOLLOW)
    except OSError as exc:
        raise ForwardDatasetReject("private_journal_missing") from exc
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600
                or not 0 < meta.st_size <= capture.MAX_BYTES):
            raise ForwardDatasetReject("private_journal_permissions_or_size_invalid")
        with os.fdopen(fd, "rb") as file:
            fd = -1
            fcntl.flock(file.fileno(), fcntl.LOCK_SH)
            raw = file.read(capture.MAX_BYTES + 1)
        if len(raw) > capture.MAX_BYTES:
            raise ForwardDatasetReject("private_journal_too_large")
        try:
            events = capture._read_rows(raw)
        except (capture.CaptureReject, ValueError, TypeError, KeyError) as exc:
            raise ForwardDatasetReject("journal_chain_or_rows_invalid") from exc
        return events, hashlib.sha256(raw).hexdigest()
    finally:
        if fd >= 0:
            os.close(fd)


def _eligible_observation(event):
    record = event["observation"]
    if "quote_receipt" not in record or record["spread_bps"] is None:
        return False
    # Existing capture schema validates venue, timestamps, OHLC and spread.
    capture.validate_observation(record)
    return True


def assemble(events, journal_sha256):
    """Use only the latest consecutive same-venue quoted suffix, >=100 bars."""
    if (not isinstance(events, list) or not events
            or not isinstance(journal_sha256, str) or len(journal_sha256) != 64
            or any(x not in "0123456789abcdef" for x in journal_sha256)):
        raise ForwardDatasetReject("journal_identity_or_content_invalid")
    # A local hash identifies *bytes*, not authentic exchange provenance.
    suffix = []
    for entry in reversed(events):
        if not isinstance(entry, dict) or not isinstance(entry.get("observation"), dict):
            raise ForwardDatasetReject("journal_entry_shape_invalid")
        current = entry["observation"]
        if not _eligible_observation(entry):
            break
        if suffix:
            later = suffix[-1]["observation"]
            prev_open = datetime.fromisoformat(current["bar_open_utc"].replace("Z", "+00:00"))
            next_open = datetime.fromisoformat(later["bar_open_utc"].replace("Z", "+00:00"))
            if ((next_open - prev_open).total_seconds() != 3600
                    or current["symbol"] != later["symbol"]
                    or current["venue_claim"] != later["venue_claim"]):
                break
        suffix.append(entry)
    if len(suffix) < foundry.MIN_BARS:
        raise ForwardDatasetReject("insufficient_consecutive_quoted_single_venue_bars")
    suffix.reverse()
    selected = suffix[-foundry.MAX_BARS:]
    first = selected[0]["observation"]
    bars = []
    for entry in selected:
        obs = entry["observation"]
        bars.append({
            "t": obs["bar_close_utc"],
            # Availability is the last contemporaneous evidence receipt.
            "available_at": obs["quote_receipt"]["quote_received_at_utc"],
            "open": obs["open"], "high": obs["high"],
            "low": obs["low"], "close": obs["close"],
            "spread_bps": obs["spread_bps"],
        })
    # Stable across rolling windows: overlapping history is one research source,
    # not a fresh independent experiment every time the journal gains a row.
    family_label = first["symbol"] + "|" + first["venue_claim"]
    source_id = "unverified-forward-" + hashlib.sha256(family_label.encode()).hexdigest()[:24]
    try:
        dataset = foundry.validate_dataset({
            "source_id": source_id,
            "symbol": first["symbol"], "interval_seconds": 3600,
            "bars": bars,
        })
    except foundry.FoundryError as exc:
        raise ForwardDatasetReject("foundry_dataset_validation_failed") from exc
    manifest = {
        "schema": SCHEMA,
        "status": "UNVERIFIED_FORWARD_RESEARCH_ONLY",
        "journal_sha256": journal_sha256,
        "dataset_sha256": foundry.digest(dataset),
        "research_source_family": source_id,
        "source_venue_claim": first["venue_claim"],
        "symbol": first["symbol"], "bar_count": len(bars),
        "first_close_utc": bars[0]["t"],
        "last_close_utc": bars[-1]["t"],
        "last_observed_at_utc": bars[-1]["available_at"],
        "provider_authenticity_verified": False,
        "broker_reconciliation_verified": False,
        "net_profitability_verified": False,
        "commission_and_slippage_verified": False,
        "production_eligible": False,
        "publication_eligible": False,
        "execution": "disabled", "real_orders": 0,
        "limitations": [
            "local journal hashes do not authenticate the exchange",
            "top-of-book spread is not commission or executable slippage",
            "no prospective broker fills, eligibility or reconciled net returns",
        ],
    }
    return {"dataset": dataset, "manifest": manifest}


def write_private(result, output):
    target = _private_path(output)
    try:
        encoded = (capture.canonical(result) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ForwardDatasetReject("dataset_json_not_serializable") from exc
    if len(encoded) > foundry.MAX_INPUT_BYTES:
        raise ForwardDatasetReject("dataset_output_too_large")
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise ForwardDatasetReject("output_must_be_new_private_file") from exc
    try:
        with os.fdopen(fd, "wb", buffering=0) as file:
            fd = -1
            if file.write(encoded) != len(encoded):
                raise ForwardDatasetReject("partial_output_write")
            os.fsync(file.fileno())
    finally:
        if fd >= 0:
            os.close(fd)
    return {"dataset_sha256": result["manifest"]["dataset_sha256"],
            "bars": result["manifest"]["bar_count"],
            "production_eligible": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline quoted-bar to research dataset gate")
    parser.add_argument("--private-journal", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args(argv)
    events, journal_sha = read_journal(args.private_journal)
    result = assemble(events, journal_sha)
    print(json.dumps(write_private(result, args.private_output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
