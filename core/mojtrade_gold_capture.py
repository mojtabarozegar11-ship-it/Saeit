"""Strict, private cTrader XAUUSD H1 log -> sole-bot signal preview bridge.

A SHA-256 footer proves byte-level self-consistency only, NOT that an actual
broker produced these records. This bridge never contacts a broker, inserts
orders, sends email, publishes signals, or treats its inputs as authorized.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import os
from pathlib import Path
import re
import stat

from core.mojtrade_demo_signal import plan_private_demo_signal, DemoSignalPlanError, SCHEMA


MARKER = "MOJTABA_GOLD_H1_CAPTURE_V1"
MAX_CAPTURE_BYTES = 40_000
ROWS = 80
HEX = re.compile(r"[0-9a-f]{64}\Z")
SESSION = re.compile(r"[0-9a-f]{32}\Z")
ALIAS = re.compile(r"[A-Za-z0-9_-]{3,40}\Z")
DEC = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")
SIGNED_DEC = re.compile(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")


class GoldCaptureError(ValueError):
    """Bounded, safe validation failure without leaking source values."""


def _value(value: str, *, name: str, signed=False):
    rule = SIGNED_DEC if signed else DEC
    if not isinstance(value, str) or not rule.fullmatch(value):
        raise GoldCaptureError(name + "_number_invalid")
    try:
        numeric = Decimal(value)
    except InvalidOperation as exc:
        raise GoldCaptureError(name + "_number_invalid") from exc
    if not numeric.is_finite():
        raise GoldCaptureError(name + "_number_nonfinite")
    return str(numeric)


def _count(value: str, *, name: str, max_count: int):
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})", value):
        raise GoldCaptureError(name + "_count_invalid")
    result = int(value)
    if result > max_count:
        raise GoldCaptureError(name + "_count_too_large")
    return result


def _time(value: str, name: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{7}Z", value,
    ):
        raise GoldCaptureError(name + "_time_format_invalid")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GoldCaptureError(name + "_time_invalid") from exc
    return result.astimezone(timezone.utc)


def capture_to_snapshot(data: bytes, *, now: datetime | None = None) -> dict:
    """Validate complete one-shot cBot log, including its exact payload hash."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_CAPTURE_BYTES:
        raise GoldCaptureError("capture_size_invalid")
    try:
        payload = data.decode("ascii")
    except UnicodeError as exc:
        raise GoldCaptureError("capture_not_ascii") from exc
    if payload.endswith("\n"):
        payload = payload[:-1]
    lines = payload.split("\n")
    if len(lines) != ROWS + 2 or any(not line.startswith(MARKER + "|") for line in lines):
        raise GoldCaptureError("capture_record_count_or_marker_invalid")
    header = lines[0].split("|")
    ending = lines[-1].split("|")
    if (len(header) != 16 or header[1] != "START"
            or len(ending) != 5 or ending[1] != "END"):
        raise GoldCaptureError("capture_envelope_invalid")
    session, alias = header[2], header[3]
    if (not SESSION.fullmatch(session) or not ALIAS.fullmatch(alias)
            or ending[2] != session or ending[3] != str(ROWS)
            or _count(header[15], name="bar", max_count=ROWS) != ROWS
            or not HEX.fullmatch(ending[4])):
        raise GoldCaptureError("capture_identity_invalid")
    packed = "\n".join(lines[:-1]).encode("ascii")
    if not hmac.compare_digest(hashlib.sha256(packed).hexdigest(), ending[4]):
        raise GoldCaptureError("capture_digest_mismatch")

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise GoldCaptureError("now_timezone_required")
    current = current.astimezone(timezone.utc)
    generated = _time(header[4], "generated")
    if not generated <= current < generated + timedelta(seconds=60):
        raise GoldCaptureError("capture_expired_or_future")

    labels = ("bid", "ask", "pip_size", "tick_size",
              "equity", "free_margin", "realized_daily_pnl", "open_stop_risk")
    amounts = {}
    for key, raw in zip(labels, header[5:13]):
        amounts[key] = _value(raw, name=key, signed=key == "realized_daily_pnl")
    positions = _count(header[13], name="open_positions", max_count=500)
    orders = _count(header[14], name="pending_orders", max_count=500)

    candles = []
    previous = None
    for line in lines[1:-1]:
        values = line.split("|")
        if len(values) != 8 or values[1] != "BAR" or values[2] != session:
            raise GoldCaptureError("candle_identity_invalid")
        opened = _time(values[3], "candle")
        if previous is not None and opened - previous != timedelta(hours=1):
            raise GoldCaptureError("candle_gap_or_duplicate")
        previous = opened
        candle = {
            "opened_at": opened.isoformat(),
            "open": _value(values[4], name="open"),
            "high": _value(values[5], name="high"),
            "low": _value(values[6], name="low"),
            "close": _value(values[7], name="close"),
        }
        candles.append(candle)

    return {
        "schema": SCHEMA,
        "owner": "mojtaba-bot-ai",
        "account_mode": "demo",
        "account_alias": alias,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "generated_at": generated.isoformat(),
        "expires_at": (generated + timedelta(seconds=60)).isoformat(),
        "quote": {
            "bid": amounts["bid"], "ask": amounts["ask"],
            "pip_size": amounts["pip_size"], "tick_size": amounts["tick_size"],
            # Captured at process server-time, NOT independent tick time.
            "observed_at": generated.isoformat(),
        },
        "candles": candles,
        "account_risk": {
            "equity": amounts["equity"],
            "realized_daily_pnl": amounts["realized_daily_pnl"],
            "open_stop_risk": amounts["open_stop_risk"],
            "free_margin": amounts["free_margin"],
            "open_positions": positions,
            "pending_orders": orders,
        },
    }


def _private_file(path: Path) -> bytes:
    if not path.is_absolute() or path.is_symlink():
        raise GoldCaptureError("private_capture_path_required")
    if (not path.parent.is_dir() or any(folder.is_symlink()
            for folder in (path.parent, *path.parent.parents))
            or stat.S_IMODE(path.parent.stat().st_mode) & 0o077):
        raise GoldCaptureError("private_capture_dir_not_0700")
    try:
        with os.fdopen(
            os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb",
        ) as reader:
            info = os.fstat(reader.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_size <= 0 or info.st_size > MAX_CAPTURE_BYTES
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise GoldCaptureError("private_capture_file_not_0600")
            raw = reader.read(MAX_CAPTURE_BYTES + 1)
            after = os.fstat(reader.fileno())
            if (len(raw) != info.st_size
                    or (info.st_size, info.st_mtime_ns) !=
                    (after.st_size, after.st_mtime_ns)):
                raise GoldCaptureError("private_capture_changed_during_read")
            return raw
    except OSError as exc:
        raise GoldCaptureError("private_capture_unavailable") from exc


def preview_private_gold_capture(path: Path, *, now=None) -> dict:
    """Private report from a read-only cBot log; does not authorize a trade."""
    raw = _private_file(path)
    source = capture_to_snapshot(raw, now=now)
    try:
        result = plan_private_demo_signal(source, now=now)
    except (DemoSignalPlanError, ValueError) as exc:
        raise GoldCaptureError("captured_market_or_risk_invalid") from exc
    result["capture_log_sha256"] = hashlib.sha256(raw).hexdigest()
    result["source_kind"] = "unverified_local_ctrader_demo_log"
    result["source_authenticated_by_broker"] = False
    return result
