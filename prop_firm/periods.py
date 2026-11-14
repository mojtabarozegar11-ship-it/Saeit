"""Deterministic, 30-day, non-overlapping promotion accounting periods.

An unfinished period cannot qualify for promotion. Days are exact elapsed
UTC 24-hour spans, not calendar-month labels or browser-selected dates.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class CompletedPeriod:
    number: int
    start: datetime
    end: datetime


def most_recent_completed_period(*, opened_at, as_of):
    if not isinstance(opened_at, datetime) or not isinstance(as_of, datetime):
        return None
    if opened_at.tzinfo is None or opened_at.utcoffset() is None:
        return None
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        return None
    start = opened_at.astimezone(timezone.utc)
    now = as_of.astimezone(timezone.utc)
    elapsed = (now - start).total_seconds()
    if elapsed < 30 * 86400:
        return None
    completed = int(elapsed // (30 * 86400))
    end = start + timedelta(days=30 * completed)
    return CompletedPeriod(
        number=completed,
        start=end - timedelta(days=30),
        end=end,
    )


def period_statistics(executions, period):
    """Signed and independently reconciled executions ONLY, interval [start, end)."""
    from collections import defaultdict
    from decimal import Decimal

    if not isinstance(period, CompletedPeriod):
        return None
    if (not isinstance(period.start, datetime)
            or not isinstance(period.end, datetime)
            or period.start.tzinfo is None or period.start.utcoffset() is None
            or period.end.tzinfo is None or period.end.utcoffset() is None
            or period.start >= period.end):
        return None
    per_day = defaultdict(lambda: Decimal("0"))
    cumulative = Decimal("0")
    for execution in executions:
        closed = getattr(execution, "closed_at", None)
        if (not isinstance(closed, datetime)
                or closed.tzinfo is None or closed.utcoffset() is None):
            # Partial records cannot support an audited monthly result.
            return None
        stamp = closed.astimezone(timezone.utc)
        if period.start <= stamp < period.end:
            # A caller must never add 'pending' or 'rejected' executions to
            # period profits, even if the account's aggregate looks positive.
            if getattr(execution, "reconciliation_status", None) != "verified":
                return None
            net = getattr(execution, "net_realized_usd", None)
            if not isinstance(net, Decimal) or not net.is_finite():
                return None
            cumulative += net
            per_day[stamp.date()] += net
    return {
        "net": cumulative,
        "trading_days": len(per_day),
        "best_day": max((Decimal("0"), *per_day.values())),
        "period": period,
    }


def completed_period_by_number(*, opened_at, as_of, period_number):
    """Return an individual completed UTC 30-day period, even if reported late.

    Explicitly disallow a zero/negative period or an unfinished future period.
    This permits sequential reconciliation of old monthly accounts.
    """
    if isinstance(period_number, bool) or not isinstance(period_number, int) or period_number < 1:
        return None
    latest = most_recent_completed_period(opened_at=opened_at, as_of=as_of)
    if latest is None or period_number > latest.number:
        return None
    start = opened_at.astimezone(timezone.utc) + timedelta(days=30 * (period_number - 1))
    return CompletedPeriod(
        number=period_number, start=start,
        end=start + timedelta(days=30),
    )
