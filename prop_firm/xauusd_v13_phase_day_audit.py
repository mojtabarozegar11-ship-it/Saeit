"""Draft-only timeline and verified-close day-count review for MOJ-PROP-01.

This is an OFFLINE mathematical audit, not independent proof that the
underlying exchange/broker feed is trustworthy. Counting days in UTC must
be reconciled with the actual simulator's contractual trading-day timezone.
It does not create paid enrollment, sign a contract, authorize funding,
move money, or place orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class PhaseDayAudit:
    phase_one_utc_days: int
    phase_two_utc_days: int
    distinct_verified_closed_positions: int
    blockers: tuple[str, ...]
    timeline_mathematically_coherent: bool
    broker_session_calendar_independently_verified: bool = False
    event_source_independently_authenticated: bool = False
    signed_customer_contract_verified: bool = False
    customer_funding_authorized: bool = False
    live_order_authorized: bool = False
    invoice_authorized: bool = False


def _instant(value, field):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} requires timezone-aware datetime")
    return value.astimezone(timezone.utc)


def audit_xauusd_v13_phase_days(*, closed_events, evaluation_started_at,
                                 phase_one_passed_at, phase_two_started_at):
    """Derive preliminary six-day-per-stage and 50-total trade checks.

    Requires an explicit independently-sourced phase-one pass and phase-two
    start timestamp. A field named 'verified' is still only a caller's
    assertion until a separate signed source adapter authenticates events.
    Refuses to infer legal trading days from the UTC aggregation.
    """
    if type(closed_events) not in (list, tuple) or len(closed_events) > 1000:
        raise ValueError("bounded immutable closed-event snapshot required")
    start = _instant(evaluation_started_at, "evaluation start")
    first_pass = _instant(phase_one_passed_at, "phase-one acceptance")
    second_start = _instant(phase_two_started_at, "phase-two start")
    end = start + timedelta(days=28)
    if not start < first_pass <= second_start < end:
        raise ValueError("phase transition timestamps are not sequential")
    days = {1: set(), 2: set()}
    positions = {}
    blockers = []
    for ev in closed_events:
        if getattr(ev, "reconciliation_status", None) != "verified":
            continue
        phase = getattr(ev, "phase", None)
        if type(phase) is not int or phase not in (1, 2):
            blockers.append("verified_close_missing_valid_phase")
            continue
        when = _instant(getattr(ev, "closed_at", None), "verified close timestamp")
        if not start <= when < end:
            blockers.append("verified_close_outside_evaluation_window")
            continue
        if (phase == 1 and when > first_pass) or (phase == 2 and when < second_start):
            blockers.append("verified_close_in_wrong_phase_window")
            continue
        source = getattr(ev, "data_source", None)
        position = getattr(ev, "external_position_id", None)
        if (type(source) is not str or not 1 <= len(source.strip()) <= 160
                or type(position) is not str or not 1 <= len(position.strip()) <= 160):
            blockers.append("verified_close_missing_stable_identity")
            continue
        key = (source.strip(), position.strip())
        prev = positions.get(key)
        if prev is not None:
            if prev != phase:
                blockers.append("verified_position_reused_across_phases")
            # Multiple fills of the same position are never distinct trades.
            continue
        positions[key] = phase
        days[phase].add(when.date().isoformat())
    if len(days[1]) < 6:
        blockers.append("phase_one_less_than_six_utc_days")
    if len(days[2]) < 6:
        blockers.append("phase_two_less_than_six_utc_days")
    if len(positions) < 50:
        blockers.append("fewer_than_fifty_distinct_verified_closes")
    # This result only checks the internally consistent arithmetic in a
    # provided dataset, not a broker's true session calendar or source trust.
    return PhaseDayAudit(
        phase_one_utc_days=len(days[1]),
        phase_two_utc_days=len(days[2]),
        distinct_verified_closed_positions=len(positions),
        blockers=tuple(dict.fromkeys(blockers)),
        timeline_mathematically_coherent=not blockers,
    )
