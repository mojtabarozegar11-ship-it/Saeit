"""Explicit, evidence-referenced market closures for historic XAUUSD bid/ask data.

A supplied calendar is only a *claim* about the broker schedule until its
origin has been independently verified. This parser cannot authenticate the
calendar, and therefore cannot authorize commercial trading or profit claims.

Closures are exact ranges of absent bar start times: [start_utc, end_utc).
One claimed closure must correspond to precisely one actual source gap.
No synthetic OHLC prices are generated, and missing bars during a supposedly
open market remain a fatal research-data error.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path


class SessionGapError(ValueError):
    pass


REASONS = {
    "scheduled_weekend": 72 * 3600,
    "session_break": 6 * 3600,
    "broker_holiday": 120 * 3600,
}
MAX_CALENDAR_BYTES = 256_000
MAX_CLOSURES = 3000


def parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise SessionGapError("session_timestamp_invalid")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SessionGapError("session_timestamp_invalid") from exc
    if date.tzinfo is None or date.utcoffset().total_seconds() != 0:
        raise SessionGapError("session_timestamp_must_be_utc")
    return date


def load_closure_claims(path: Path, timeframe_minutes: int) -> tuple[list[dict], str]:
    """Read a bounded, *unverified* broker-specific closure manifest."""
    if type(timeframe_minutes) is not int or timeframe_minutes not in (1, 5, 10):
        raise SessionGapError("session_timeframe_invalid")
    if path.is_symlink() or not path.is_file():
        raise SessionGapError("session_calendar_not_regular")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_CALENDAR_BYTES + 1)
    except OSError as exc:
        raise SessionGapError("session_calendar_unreadable") from exc
    if len(raw) > MAX_CALENDAR_BYTES:
        raise SessionGapError("session_calendar_too_large")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SessionGapError("session_calendar_invalid_json") from exc
    if (
        not isinstance(document, dict)
        or set(document) != {
            "schema_version", "broker", "symbol", "timeframe_minutes", "closures"
        }
        or document["schema_version"] != 1
        or document["broker"] != "LiteFinance"
        or document["symbol"] != "XAUUSD"
        or type(document["timeframe_minutes"]) is not int
        or document["timeframe_minutes"] != timeframe_minutes
    ):
        raise SessionGapError("session_calendar_broker_symbol_or_schema_invalid")
    records = document["closures"]
    if not isinstance(records, list) or len(records) > MAX_CLOSURES:
        raise SessionGapError("session_calendar_count_invalid")
    interval_seconds = timeframe_minutes * 60
    checked = []
    previous_end = None
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "start_utc", "end_utc", "reason", "evidence_ref"
        }:
            raise SessionGapError("session_closure_schema_invalid")
        start = parse_utc(record["start_utc"])
        end = parse_utc(record["end_utc"])
        reason = record["reason"]
        reference = record["evidence_ref"]
        if (
            reason not in REASONS
            or not isinstance(reference, str)
            or not 8 <= len(reference.strip()) <= 180
            or any(ord(c) < 32 for c in reference)
        ):
            raise SessionGapError("session_closure_evidence_required")
        seconds = (end - start).total_seconds()
        if (
            seconds < interval_seconds
            or seconds > REASONS[reason]
            or seconds % interval_seconds
            or int(start.timestamp()) % interval_seconds
            or int(end.timestamp()) % interval_seconds
            or previous_end is not None and start <= previous_end
        ):
            raise SessionGapError("session_closure_invalid_or_overlapping")
        checked.append({
            "start": start, "end": end,
            "reason": reason, "evidence_ref": reference.strip(),
        })
        previous_end = end
    return checked, hashlib.sha256(raw).hexdigest()


def reconcile_gaps(bars: list, timeframe_minutes: int, claims: list[dict]) -> int:
    """Only absent bar timestamps exactly covered by claimed closures pass.

    Claims never allow a malformed within-session gap or a missing interval
    without an exact external evidence reference.
    """
    interval = timeframe_minutes * 60
    found = 0
    for previous, following in zip(bars, bars[1:]):
        seconds = (following.time - previous.time).total_seconds()
        if seconds == interval:
            continue
        expected_start = previous.time.timestamp() + interval
        if seconds <= interval or seconds % interval:
            raise SessionGapError("market_quote_timeline_invalid")
        if found >= len(claims):
            raise SessionGapError("unexplained_market_quote_gap")
        claim = claims[found]
        if (
            int(claim["start"].timestamp()) != int(expected_start)
            or claim["end"] != following.time
        ):
            raise SessionGapError("gap_does_not_match_exact_closure")
        found += 1
    if found != len(claims):
        raise SessionGapError("unused_or_fabricated_closure_claim")
    return found
