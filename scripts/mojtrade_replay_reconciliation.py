#!/usr/bin/env python3
"""Offline, append-only reconciliation of research slots and simulated fills.

This module never releases a risk reservation. Even a zero simulated fill is
NOT equivalent to broker-verified zero exposure. No broker/network operations.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from decimal import Decimal, InvalidOperation
from pathlib import Path


SCHEMA = "mojtrade.shadow-reconciliation.v1"
MAX_LOG_BYTES = 16_000_000
MAX_RECORDS = 10_000


class ReconciliationReject(ValueError):
    """Unsafe, inconsistent or corrupted research accounting evidence."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _check(obj, checksum, context):
    if (not isinstance(obj, dict) or not isinstance(obj.get(checksum), str) or
            obj[checksum] != _digest({k: v for k, v in obj.items() if k != checksum})):
        raise ReconciliationReject(context + "_hash_invalid")


def _amount(value, key):
    if isinstance(value, bool) or not isinstance(value, str) or len(value) > 40:
        raise ReconciliationReject(key + "_invalid")
    try:
        out = Decimal(value)
    except InvalidOperation as exc:
        raise ReconciliationReject(key + "_invalid") from exc
    if not out.is_finite() or out < 0 or out > Decimal("1e15") or out.as_tuple().exponent < -12:
        raise ReconciliationReject(key + "_out_of_bounds")
    return out


def build_receipt(handoff, replay):
    _check(handoff, "handoff_sha256", "handoff")
    _check(replay, "report_sha256", "twin")
    if (handoff.get("mode") != "RESEARCH_ONLY" or handoff.get("orders") != 0 or
            handoff.get("broker_eligible") is not False or
            handoff.get("public_signals") != 0 or
            handoff.get("execution") != "disabled" or
            replay.get("mode") != "RESEARCH_SIMULATION_ONLY" or
            replay.get("real_orders") != 0 or replay.get("public_signals") != 0 or
            replay.get("broker_connected") is not False):
        raise ReconciliationReject("live_or_untrusted_execution_mode")
    risk = handoff.get("risk_response")
    if not isinstance(risk, dict):
        raise ReconciliationReject("risk_response_missing")
    _check(risk, "report_sha256", "risk")
    if (risk.get("mode") != "RESEARCH_ONLY" or risk.get("orders") != 0 or
            risk.get("public_signals") != 0 or risk.get("execution") != "disabled"):
        raise ReconciliationReject("risk_mode_invalid")
    decisions = risk.get("decisions")
    fills = replay.get("receipts")
    if not isinstance(decisions, list) or len(decisions) != 1 or not isinstance(fills, list) or len(fills) != 1:
        raise ReconciliationReject("one_to_one_replay_required")
    decision, fill = decisions[0], fills[0]
    _check(decision, "receipt_sha256", "risk_decision")
    _check(fill, "receipt_sha256", "twin_fill")
    if (decision.get("status") != "RESEARCH_SLOT_RESERVED" or
            decision.get("request_id") != fill.get("intent_id") or
            decision.get("strategy_id") != handoff.get("strategy_id") or
            fill.get("strategy_id") != decision.get("strategy_id") or
            decision.get("symbol") != replay.get("symbol") or
            fill.get("broker_order_submitted") is not False or
            replay.get("hypothetical_intents_evaluated") != 1):
        raise ReconciliationReject("risk_twin_lineage_mismatch")
    requested = _amount(fill.get("requested_quantity"), "requested_quantity")
    filled = _amount(fill.get("filled_quantity"), "filled_quantity")
    cancelled = _amount(fill.get("cancelled_quantity"), "cancelled_quantity")
    if requested <= 0 or filled + cancelled != requested:
        raise ReconciliationReject("quantity_conservation_failed")
    partial = fill.get("partial_fills")
    if (not isinstance(partial, list) or len(partial) > 128 or
            any(not isinstance(row, dict) or set(row) != {"size", "price"} for row in partial)):
        raise ReconciliationReject("partial_fills_schema_invalid")
    if sum((_amount(row["size"], "fill_size") for row in partial), Decimal(0)) != filled:
        raise ReconciliationReject("partial_fills_conservation_failed")
    if (filled == 0 and (fill.get("average_fill_price") is not None or
                         fill.get("status") not in {"FOK_DEPTH_INSUFFICIENT",
                                                     "SLIPPAGE_CAP_OR_NO_LIQUIDITY",
                                                     "EXPIRED_BEFORE_EXECUTION",
                                                     "VENUE_HALTED", "NO_EXECUTABLE_EVENT"})):
        raise ReconciliationReject("unfilled_status_inconsistent")
    if filled > 0:
        weighted = sum((_amount(row["size"], "fill_size") *
                        _amount(row["price"], "fill_price") for row in partial), Decimal(0))
        avg = _amount(fill.get("average_fill_price"), "average_fill_price")
        if avg <= 0 or abs(avg * filled - weighted) > Decimal("1e-8"):
            raise ReconciliationReject("average_fill_inconsistent")
        if fill.get("status") != ("FILLED" if cancelled == 0 else "PARTIAL_CANCELLED"):
            raise ReconciliationReject("filled_status_inconsistent")
    status = "SIMULATED_UNFILLED" if filled == 0 else (
        "SIMULATED_FILLED" if cancelled == 0 else "SIMULATED_PARTIAL")
    receipt = {
        "schema": SCHEMA, "mode": "RESEARCH_ONLY",
        "account_id": risk.get("account_id"),
        "request_id": decision["request_id"],
        "strategy_id": decision["strategy_id"],
        "symbol": decision["symbol"],
        "status": status,
        "requested_quantity": str(requested), "simulated_filled_quantity": str(filled),
        "simulated_cancelled_quantity": str(cancelled),
        "risk_receipt_sha256": decision["receipt_sha256"],
        "twin_fill_receipt_sha256": fill["receipt_sha256"],
        "risk_reservation": "REMAINS_RESERVED",
        "broker_exposure_verified": False, "real_orders": 0,
        "release_eligible": False,
        "limitations": ["simulated fills are not broker evidence",
                        "no reservation release or netting performed",
                        "immutable checkpoint off-host still required"],
    }
    if not isinstance(receipt["account_id"], str) or not 1 <= len(receipt["account_id"]) <= 64:
        raise ReconciliationReject("account_id_invalid")
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt


def _verify_log(data):
    if data and not data.endswith(b"\n"):
        raise ReconciliationReject("journal_truncated")
    rows = []
    previous = "0" * 64
    for raw in data.splitlines():
        try:
            row = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ReconciliationReject("journal_json_invalid") from exc
        if (not isinstance(row, dict) or set(row) !=
                {"sequence", "previous_sha256", "receipt", "entry_sha256"} or
                row["sequence"] != len(rows) + 1 or row["previous_sha256"] != previous):
            raise ReconciliationReject("journal_chain_invalid")
        _check(row["receipt"], "receipt_sha256", "journal_receipt")
        _check(row, "entry_sha256", "journal_entry")
        previous = row["entry_sha256"]
        rows.append(row)
    return rows


def record_receipt(handoff, replay, private_log):
    receipt = build_receipt(handoff, replay)
    path = Path(private_log)
    parent = path.parent
    if (parent.is_symlink() or not parent.is_dir() or
            stat.S_IMODE(parent.stat().st_mode) != 0o700 or path.is_symlink()):
        raise ReconciliationReject("private_parent_or_symlink_invalid")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600 or
                metadata.st_uid != os.geteuid() or metadata.st_nlink != 1):
            raise ReconciliationReject("journal_permissions_invalid")
        with os.fdopen(fd, "r+b", buffering=0) as handle:
            fd = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            raw = handle.read(MAX_LOG_BYTES + 1)
            if len(raw) > MAX_LOG_BYTES:
                raise ReconciliationReject("journal_capacity")
            rows = _verify_log(raw)
            for row in rows:
                existing = row["receipt"]
                if (existing["account_id"], existing["request_id"]) == (
                        receipt["account_id"], receipt["request_id"]):
                    if existing["receipt_sha256"] != receipt["receipt_sha256"]:
                        raise ReconciliationReject("request_id_conflicting_reconciliation")
                    return {"receipt": existing, "sequence": row["sequence"],
                            "entry_sha256": row["entry_sha256"]}
            if len(rows) >= MAX_RECORDS:
                raise ReconciliationReject("journal_records_exhausted")
            row = {"sequence": len(rows) + 1,
                   "previous_sha256": rows[-1]["entry_sha256"] if rows else "0" * 64,
                   "receipt": receipt}
            row["entry_sha256"] = _digest(row)
            encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            if len(raw) + len(encoded) > MAX_LOG_BYTES:
                raise ReconciliationReject("journal_capacity")
            handle.seek(0, os.SEEK_END)
            if handle.write(encoded) != len(encoded):
                raise ReconciliationReject("journal_partial_write")
            os.fsync(handle.fileno())
            return {"receipt": receipt, "sequence": row["sequence"],
                    "entry_sha256": row["entry_sha256"]}
    finally:
        if fd >= 0:
            os.close(fd)


def verify_log(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ReconciliationReject("journal_file_invalid")
    with path.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        data = handle.read(MAX_LOG_BYTES + 1)
    if len(data) > MAX_LOG_BYTES:
        raise ReconciliationReject("journal_capacity")
    return len(_verify_log(data))
