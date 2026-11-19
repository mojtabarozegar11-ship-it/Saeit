"""Conservative unique CLOSED-trade counting for one 28-day MOJ PROP cohort.

Counts closed positions, not order requests or separate fills. Input must be
authoritatively sourced and reconciled: one stable external position ID from
the broker/simulator per position, plus source identifier. No browser-supplied
trade counts, virtual positions, duplicated phase records or post-deadline
activity can satisfy the fifty-trade condition.
"""
from dataclasses import dataclass
from datetime import timedelta

from .social_policy import aware_utc, DURATION_DAYS
from .rules import POLICY


@dataclass(frozen=True)
class ChallengeTradeCount:
    valid_closed_positions: int
    manual_positions: int
    bot_positions: int
    unknown_origin_positions: int
    uncountable_events: int
    sufficient: bool
    required: int = 50


def count_challenge_trades(executions, *, paid_at, required=50):
    start = aware_utc(paid_at, "paid_at")
    end = start + timedelta(days=DURATION_DAYS)
    # A caller must not defeat v1.2 qualification by requesting fewer than
    # the owner-approved fifty independently verified closed positions.
    if type(required) is not int or required < POLICY.min_closed_trades_per_challenge:
        raise ValueError("Required trade count cannot be below the canonical policy")
    if executions is None:
        raise ValueError("Trusted trade ledger required")
    positions = {}
    # A verified provider position with conflicting close times straddling
    # the purchase boundary cannot be treated as independently CLOSED within
    # the 28-day cohort merely because one of its rows is in-window.
    out_of_window_positions = set()
    uncountable = 0
    for event in executions:
        close = getattr(event, "closed_at", None)
        if (getattr(event, "reconciliation_status", None) != "verified"
                or close is None):
            uncountable += 1
            continue
        closed = aware_utc(close, "closed_at")
        position = getattr(event, "external_position_id", "")
        source = getattr(event, "data_source", "")
        if (type(position) is not str or not position.strip()
                or type(source) is not str or not source.strip()):
            uncountable += 1
            continue
        key = (source.strip(), position.strip())
        if not start <= closed < end:
            uncountable += 1
            out_of_window_positions.add(key)
            continue
        # Any duplicated close/fill shares the same position key, even when
        # the duplicate is booked in a separate phase account.
        origin = getattr(event, "execution_origin", "unknown")
        origin = origin if origin in ("manual", "bot", "unknown") else "unknown"
        if key not in positions:
            positions[key] = origin
        elif positions[key] != origin:
            # A single broker position must have one attributable execution
            # origin. Contradictory independently reconciled fills cannot
            # be classified by whichever row happens to arrive first.
            # Exclude the whole position from qualification until the
            # provider resolves its identity; never trust iterator order.
            positions[key] = "conflicting"
    # This pass is order-independent: an outside-window verified close must
    # invalidate the same position whether it arrived before or after its
    # in-window record. Pending/rejected rows never gain this authority.
    for key in out_of_window_positions:
        if key in positions:
            positions[key] = "conflicting"
    conflicted = sum(origin == "conflicting" for origin in positions.values())
    uncountable += conflicted
    positions = {key: origin for key, origin in positions.items()
                 if origin != "conflicting"}
    count = len(positions)
    return ChallengeTradeCount(
        valid_closed_positions=count,
        manual_positions=sum(p == "manual" for p in positions.values()),
        bot_positions=sum(p == "bot" for p in positions.values()),
        unknown_origin_positions=sum(p == "unknown" for p in positions.values()),
        uncountable_events=uncountable,
        sufficient=count >= required,
        required=required,
    )
