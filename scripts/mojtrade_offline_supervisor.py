#!/usr/bin/env python3
"""GitHub-independent, offline MojTrade RESEARCH STATUS supervisor.

Reads frozen scientific evidence, records only state transitions, and NEVER
connects to a broker, executes a trade, or publishes signals. It is not a
production trading daemon or a financial performance certification.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

import mojtrade_independent_validation as oos
import mojtrade_dependency_diagnostics as dep


SCHEMA = "mojtrade.offline-supervisor.v1"
CONFIG_KEYS = {"schema", "foundry_report", "training_data", "unseen_data",
               "private_oos_ledger"}
MAX_INPUT_BYTES = 3_000_000
MAX_EVENT_BYTES = 5_000_000
MAX_EVENTS = 500
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class SupervisorReject(ValueError):
    """Unsafe local supervisor configuration or audit storage."""


def _private_dir(path):
    folder = Path(path)
    if (not folder.is_dir() or folder.is_symlink() or
            stat.S_IMODE(folder.stat().st_mode) != 0o700 or
            folder.stat().st_uid != os.geteuid()):
        raise SupervisorReject("private_0700_state_directory_required")
    return folder


def _regular_bytes(path, max_bytes, *, private=False):
    file = Path(path)
    if not file.is_absolute() or file.is_symlink():
        raise SupervisorReject("unsafe_absolute_regular_file_required")
    try:
        fd = os.open(file, os.O_RDONLY | os.O_NONBLOCK | O_NOFOLLOW)
    except OSError as exc:
        raise SupervisorReject("file_unavailable") from exc
    try:
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or
                s.st_uid != os.geteuid() or
                (stat.S_IMODE(s.st_mode) != 0o600 if private else bool(s.st_mode & 0o022)) or
                s.st_size > max_bytes):
            raise SupervisorReject("file_permission_or_size_invalid")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            raw = handle.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise SupervisorReject("file_too_large")
            return raw
    finally:
        if fd >= 0:
            os.close(fd)


def _read_json(path, *, private=False):
    try:
        return json.loads(_regular_bytes(path, MAX_INPUT_BYTES, private=private))
    except (UnicodeError, ValueError) as exc:
        raise SupervisorReject("invalid_json_or_local_file") from exc


def _config(path):
    cfg = _read_json(Path(path), private=True)
    if (not isinstance(cfg, dict) or set(cfg) != CONFIG_KEYS or
            cfg["schema"] != SCHEMA):
        raise SupervisorReject("config_schema_invalid")
    for key in CONFIG_KEYS - {"schema"}:
        p = cfg[key]
        if not isinstance(p, str) or not Path(p).is_absolute() or "\x00" in p:
            raise SupervisorReject("config_absolute_local_paths_only")
    return cfg


def _frozen_receipt(path, report_sha, expected):
    path = Path(path)
    _private_dir(path.parent)
    raw = _regular_bytes(path, oos.MAX_LEDGER_BYTES, private=True)
    try:
        rows = oos._read_journal(raw)
    except oos.ValidationReject as exc:
        raise SupervisorReject("frozen_journal_integrity_invalid") from exc
    matches = [row["receipt"] for row in rows if
               row["receipt"].get("report_sha256") == report_sha]
    if len(matches) != 1 or matches[0] != expected:
        raise SupervisorReject("original_holdout_receipt_missing_or_changed")
    return matches[0]


def _stop_flag(folder):
    stop = folder / "STOP"
    # A symlink or malformed STOP is also a stop: never reinterpret it as run.
    return stop.exists() or stop.is_symlink()


def inspect(config_path, state_dir):
    """Read-only evidence scan. No code path can authorize external actions."""
    folder = _private_dir(state_dir)
    base = {"schema": SCHEMA, "mode": "LOCAL_RESEARCH_STATUS_ONLY",
            "execution": "disabled", "real_orders": 0, "public_signals": 0,
            "broker_eligible": False, "publish_eligible": False,
            "commercial_ready": False, "git_hub_runtime_dependency": False}
    if _stop_flag(folder):
        return {**base, "state": "OPERATOR_STOPPED", "evidence_receipt_sha256": None,
                "blockers": ["local_stop_flag_present", "no_owner_trading_release"]}
    try:
        cfg = _config(config_path)
        report = _read_json(cfg["foundry_report"])
        train = _read_json(cfg["training_data"])
        unseen = _read_json(cfg["unseen_data"])
        expected = oos.assess(report, train, unseen)
        frozen = _frozen_receipt(cfg["private_oos_ledger"], report["report_sha256"], expected)
        diagnostic = dep.audit(report, train, unseen, frozen)
    except (SupervisorReject, oos.ValidationReject, oos.foundry.FoundryError,
            dep.DependencyReject, KeyError, TypeError) as exc:
        return {**base, "state": "BLOCKED_EVIDENCE", "evidence_receipt_sha256": None,
                "blockers": ["unavailable_or_inconsistent_local_evidence",
                             type(exc).__name__ + ":" + str(exc)[:96],
                             "no_owner_trading_release"]}
    return {**base, "state": "RESEARCH_EVIDENCE_OBSERVED_UNVERIFIED",
            "evidence_receipt_sha256": frozen["receipt_sha256"],
            "dependence_diagnostic_sha256": diagnostic["receipt_sha256"],
            "candidate_count": diagnostic["family_size"],
            "blockers": ["source_and_observation_time_not_authenticated",
                         "no_prospective_forward_broker_reconciliation",
                         "no_calibrated_financial_edge", "no_owner_trading_release"]}


def _read_event_journal(raw):
    if raw and not raw.endswith(b"\n"):
        raise SupervisorReject("journal_partial_write")
    rows, previous = [], "0" * 64
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise SupervisorReject("journal_invalid_json") from exc
        if (not isinstance(row, dict) or set(row) !=
                {"sequence", "previous_sha256", "event", "changed_at_utc", "entry_sha256"} or
                row["sequence"] != len(rows) + 1 or
                row["previous_sha256"] != previous or
                row["entry_sha256"] != oos.foundry.digest(
                    {k: v for k, v in row.items() if k != "entry_sha256"})):
            raise SupervisorReject("journal_hash_chain_invalid")
        if not isinstance(row["event"], dict) or row["event"].get("schema") != SCHEMA:
            raise SupervisorReject("journal_event_schema_invalid")
        previous = row["entry_sha256"]
        rows.append(row)
    return rows


def record_if_changed(event, state_dir, *, now=None):
    """Only durable *transitions* count; duplicate polls never add reports."""
    folder = _private_dir(state_dir)
    path = folder / "state-changes.jsonl"
    if path.is_symlink():
        raise SupervisorReject("journal_symlink_invalid")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | O_NOFOLLOW, 0o600)
    try:
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode) != 0o600 or
                s.st_nlink != 1 or s.st_uid != os.geteuid()):
            raise SupervisorReject("journal_permissions_invalid")
        with os.fdopen(fd, "r+b", buffering=0) as handle:
            fd = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            raw = handle.read(MAX_EVENT_BYTES + 1)
            if len(raw) > MAX_EVENT_BYTES:
                raise SupervisorReject("journal_capacity_exceeded")
            rows = _read_event_journal(raw)
            if rows and rows[-1]["event"] == event:
                return {"transition_written": False, "sequence": rows[-1]["sequence"],
                        "entry_sha256": rows[-1]["entry_sha256"]}
            if len(rows) >= MAX_EVENTS:
                raise SupervisorReject("journal_capacity_exceeded")
            timestamp = now or datetime.now(timezone.utc)
            if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
                raise SupervisorReject("timestamp_must_be_timezone_aware")
            row = {"sequence": len(rows) + 1,
                   "previous_sha256": rows[-1]["entry_sha256"] if rows else "0" * 64,
                   "event": event,
                   "changed_at_utc": timestamp.astimezone(timezone.utc).isoformat()}
            row["entry_sha256"] = oos.foundry.digest(row)
            data = (oos.foundry.canonical(row) + "\n").encode()
            if len(raw) + len(data) > MAX_EVENT_BYTES:
                raise SupervisorReject("journal_capacity_exceeded")
            handle.seek(0, os.SEEK_END)
            if handle.write(data) != len(data):
                raise SupervisorReject("journal_short_write")
            os.fsync(handle.fileno())
            return {"transition_written": True, "sequence": row["sequence"],
                    "entry_sha256": row["entry_sha256"]}
    finally:
        if fd >= 0:
            os.close(fd)


def inspect_and_record(config_path, state_dir):
    event = inspect(config_path, state_dir)
    record = record_if_changed(event, state_dir)
    return {"state": event["state"], "new_material_transition": record["transition_written"],
            "journal_sequence": record["sequence"], "real_orders": 0,
            "public_signals": 0, "commercial_ready": False,
            "blockers": event["blockers"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Zero-network local research evidence monitor")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--watch", action="store_true", help="Poll until operator STOP or Ctrl-C")
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    if not 30 <= args.interval_seconds <= 3600:
        parser.error("interval_seconds must be 30..3600")
    while True:
        result = inspect_and_record(args.config, args.state_dir)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        if not args.watch or result["state"] == "OPERATOR_STOPPED":
            break
        try:
            time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
