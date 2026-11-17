"""Pure no-side-effects check for duplicate broker position IDs across sources."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class CrossSourceCollision:
    collisions: int
    checked_verified_events: int
    independently_authenticated: bool = False
    live_order_authorized: bool = False
    checkout_authorized: bool = False


def assess_closed_position_source_conflicts(executions, *, evaluation_started_at):
    """Warn on same closed position ID from distinct upstream sources.

    Historical counting uses (source, position_id), which can count one
    imported position twice when two adapters replay it. This NEW v1.3
    check fails qualification closed pending private reconciliation, rather
    than assuming either upstream source uniquely owns the position ID.
    An equal position ID at separate brokers might be coincidental; the
    conservative outcome is review-only, NEVER customer disqualification.
    """
    if type(executions) not in (list, tuple) or len(executions) > 1000:
        raise ValueError("bounded source ledger required")
    if (type(evaluation_started_at) is not datetime
            or evaluation_started_at.tzinfo is None
            or evaluation_started_at.utcoffset() is None):
        raise ValueError("timezone-aware evaluation start required")
    begin = evaluation_started_at.astimezone(timezone.utc)
    end = begin + timedelta(days=28)
    by_position = {}
    conflicts = set()
    checked = 0
    for event in executions:
        if getattr(event, "reconciliation_status", None) != "verified":
            continue
        closed = getattr(event, "closed_at", None)
        if type(closed) is not datetime or closed.tzinfo is None or closed.utcoffset() is None:
            raise ValueError("verified close timestamp must be timezone-aware")
        timestamp = closed.astimezone(timezone.utc)
        if not begin <= timestamp < end:
            continue
        source = getattr(event, "data_source", None)
        position = getattr(event, "external_position_id", None)
        if (type(source) is not str or not 0 < len(source.strip()) <= 160
                or type(position) is not str or not 0 < len(position.strip()) <= 160):
            continue
        key = position.strip()
        value = source.strip()
        checked += 1
        previous = by_position.setdefault(key, value)
        if previous != value:
            conflicts.add(key)
    return CrossSourceCollision(
        collisions=len(conflicts), checked_verified_events=checked,
    )
