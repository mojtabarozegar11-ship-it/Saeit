"""MOJ-PROP-01 prospective v1.4.1 two-stage DEMO event-replay engine.

Deterministic financial mathematics from a bounded, immutable snapshot:
- 28-day sequential phase timeline with explicit acceptance transitions
- 50 distinct FULLY closed positions TOTAL, not fills, across both phases
- 6 UTC close days per phase; phase profits 9.6% and 6%
- best profitable day <=32% of each phase's realized net profit
- floating-equity 4% daily / 8% overall breaches are sticky
- duplicates, conflicts, partial closes, bad provenance labels fail closed
- social-post >=672h is a SEPARATE clock and cannot create a paid enrollment.

IMPORTANT: 'verified' flags and SHA-shaped evidence fields are caller CLAIMS.
A trusted adapter must authenticate source identity and prove COMPLETE histories,
timezones, customer rights, settlement, broker permission and actual funding.
This module is READ-ONLY and NEVER creates/approves money, enrollment, broker
accounts, real orders, payouts or contracts. No HTTP, ORM, network or secrets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re

from .plan1_v14_social_or_50_terms import review_prospective_terms
from .xauusd_v13_draft_terms import draft_gold_terms_v13
from .plan1_v14_social_or_28d_review import Social28DayReview

D = Decimal
CHALLENGE_TIME = timedelta(days=28)
CAPITAL = D("100")
DAILY_LOSS = D("4")
TOTAL_LOSS = D("8")
BEST_DAY_SHARE = D("0.32")
MAX_EVENTS = 5000
SHA = re.compile(r"[0-9a-f]{64}\Z")
REFERENCE = re.compile(r"CHALLENGE-[A-Z0-9]{16,40}\Z")
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}\Z")


@dataclass(frozen=True)
class SimulatedClosedFill:
    phase: int
    data_source: str
    external_event_id: str
    external_position_id: str
    symbol: str
    closed_at: datetime
    gross_realized_usd: str
    total_fees_usd: str
    position_fully_closed: bool
    reconciliation_status: str
    evidence_sha256: str


@dataclass(frozen=True)
class SimulatedEquityMark:
    phase: int
    data_source: str
    external_event_id: str
    observed_at: datetime
    equity_usd: str
    is_utc_day_open: bool
    reconciliation_status: str
    evidence_sha256: str


@dataclass(frozen=True)
class EngineSnapshot:
    challenge_ref: str
    accepted_terms_sha256: str
    evaluation_started_at: datetime
    phase_one_accepted_at: datetime | None
    phase_two_started_at: datetime | None
    phase_two_completed_at: datetime | None
    as_of: datetime
    closed_fills: tuple[SimulatedClosedFill, ...]
    equity_marks: tuple[SimulatedEquityMark, ...]


@dataclass(frozen=True)
class SimulatedPhaseDecision:
    phase: int
    verified_closed_positions: int
    verified_utc_trading_days: int
    realized_net_usd: Decimal
    best_realized_day_usd: Decimal
    target_net_usd: Decimal
    lowest_verified_equity_usd: Decimal | None
    mathematical_pass: bool
    risk_breached: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class ChallengeReplayDecision:
    challenge_ref: str
    contract_version: str
    terms_sha256: str
    snapshot_sha256: str
    evaluation_deadline_utc: str
    assessment_utc: str
    phase_one: SimulatedPhaseDecision
    phase_two: SimulatedPhaseDecision
    combined_unique_closed_positions: int
    replayed_duplicate_event_count: int
    phase_math_complete: bool
    social_math_complete: bool
    combined_math_complete: bool
    state: str
    blockers: tuple[str, ...]
    # These NEVER change in this source-only engine.
    source_authenticity_independently_proven: bool = False
    ledger_completeness_independently_proven: bool = False
    broker_session_calendar_independently_proven: bool = False
    merchant_and_customer_law_approved: bool = False
    social_post_independently_verified: bool = False
    signed_buyer_terms_verified: bool = False
    company_real_funding_verified: bool = False
    fee_collection_authorized: bool = False
    paid_enrollment_authorized: bool = False
    real_broker_orders_authorized: bool = False
    payout_authorized: bool = False


def _utc(value, name):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name}: timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def _money(value, name, *, nonnegative=False):
    if type(value) not in (str, Decimal, int):
        raise ValueError(f"{name}: exact numeric string/Decimal required")
    try:
        d = D(str(value))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(f"{name}: invalid money") from exc
    if not d.is_finite() or abs(d) > D("1000000000") or d.as_tuple().exponent < -4:
        raise ValueError(f"{name}: finite bounded exact 4-decimal money required")
    if nonnegative and d < 0:
        raise ValueError(f"{name}: negative value rejected")
    return d


def _id(value, name):
    if type(value) is not str or IDENTITY.fullmatch(value) is None:
        raise ValueError(f"{name}: stable bounded identifier required")
    return value


def _phase(value):
    if type(value) is not int or value not in (1, 2):
        raise ValueError("exact phase 1 or 2 required")
    return value


def _evidence(value):
    if type(value) is not str or SHA.fullmatch(value) is None or value == "0" * 64:
        raise ValueError("nonzero evidence SHA256 syntax required")


def _phase_result(phase, fills, marks, *, opened, ended, as_of, required_net):
    reasons = []
    net_by_day = {}
    completed_positions = set()
    for key, entries in fills.items():
        if key[0] != phase:
            continue
        entries = sorted(entries, key=lambda x: (x[1], x[0].external_event_id))
        finals = [i for i, (event, when, gross, fees) in enumerate(entries)
                  if event.position_fully_closed is True]
        if len(finals) != 1 or finals[0] != len(entries) - 1:
            reasons.append(f"phase_{phase}_position_not_fully_closed_or_final_out_of_order")
            continue
        completed_positions.add(key)
        for event, when, gross, fees in entries:
            day = when.date().isoformat()
            net_by_day[day] = net_by_day.get(day, D("0")) + gross - fees
    net = sum(net_by_day.values(), D("0"))
    best_day = max((D("0"), *net_by_day.values()))
    # A valid UTC trading day requires at least one completely closed position.
    trade_days = {
        max(event[1] for event in entries).date().isoformat()
        for key, entries in fills.items() if key[0] == phase
        and key in completed_positions
    }
    stage_marks = sorted((x for x in marks if x[0].phase == phase),
                         key=lambda x: (x[1], x[0].external_event_id))
    day_open = {}
    lowest = None
    for mark, when, equity in stage_marks:
        day = when.date().isoformat()
        lowest = equity if lowest is None else min(lowest, equity)
        if mark.is_utc_day_open:
            if day in day_open:
                reasons.append(f"phase_{phase}_multiple_utc_day_open_marks")
            else:
                day_open[day] = (when, equity)
    phase_fill_sources = {key[1] for key in fills if key[0] == phase}
    phase_mark_sources = {row[0].data_source for row in stage_marks}
    if (len(phase_fill_sources) != 1
            or phase_mark_sources != phase_fill_sources):
        reasons.append(f"phase_{phase}_execution_equity_source_mismatch")
    if stage_marks:
        opening = stage_marks[0]
        if opening[0].is_utc_day_open is not True or opening[2] != CAPITAL:
            reasons.append(f"phase_{phase}_initial_equity_not_equal_to_plan_capital")
        # The final mark must reflect all fully closed trade P&L with
        # nothing silently added to or subtracted from the demo equity.
        # This cannot independently prove that all positions are flat.
        last_close = max((event[1] for key, entries in fills.items()
                          if key[0] == phase and key in completed_positions
                          for event in entries), default=None)
        if last_close is not None:
            if stage_marks[-1][1] < last_close:
                reasons.append(f"phase_{phase}_terminal_equity_mark_predates_last_close")
            if stage_marks[-1][2] != CAPITAL + net:
                reasons.append(f"phase_{phase}_terminal_equity_pnl_mismatch")
    marks_by_day = {}
    for mark, when, equity in stage_marks:
        day = when.date().isoformat()
        marks_by_day.setdefault(day, []).append((mark, when, equity))
    for day, entries in marks_by_day.items():
        opening = day_open.get(day)
        if opening is None or entries[0][1] != opening[0]:
            reasons.append(f"phase_{phase}_missing_or_late_day_open_equity")
            continue
        floor = opening[1] - DAILY_LOSS
        for mark, when, equity in entries:
            if equity <= floor:
                reasons.append(f"phase_{phase}_daily_drawdown_breached")
            if equity <= CAPITAL - TOTAL_LOSS:
                reasons.append(f"phase_{phase}_total_drawdown_breached")
    for day in trade_days:
        if day not in marks_by_day:
            reasons.append(f"phase_{phase}_missing_equity_for_trading_day")
    if not stage_marks:
        reasons.append(f"phase_{phase}_equity_history_missing")
    if len(trade_days) < 6:
        reasons.append(f"phase_{phase}_fewer_than_six_utc_trading_days")
    if net < required_net:
        reasons.append(f"phase_{phase}_profit_target_not_met")
    if best_day > net * BEST_DAY_SHARE:
        reasons.append(f"phase_{phase}_best_day_consistency_exceeded")
    if ended is None:
        reasons.append(f"phase_{phase}_acceptance_transition_not_recorded")
    elif ended < opened:
        reasons.append(f"phase_{phase}_acceptance_before_start")
    if not fills or not any(key[0] == phase for key in fills):
        reasons.append(f"phase_{phase}_no_closed_positions")
    reasons = tuple(dict.fromkeys(reasons))
    breach = any("drawdown_breached" in x for x in reasons)
    return SimulatedPhaseDecision(
        phase=phase, verified_closed_positions=len(completed_positions),
        verified_utc_trading_days=len(trade_days), realized_net_usd=net,
        best_realized_day_usd=best_day, target_net_usd=required_net,
        lowest_verified_equity_usd=lowest,
        mathematical_pass=not reasons, risk_breached=breach, blockers=reasons,
    )


def replay_simulated_challenge(*, snapshot: EngineSnapshot,
                               social: Social28DayReview | None = None) -> ChallengeReplayDecision:
    """Replay one immutable candidate snapshot; never authorize commercial use.

    This is arithmetic state reconstruction, NOT a real broker feed handler.
    No externally verified settlement/account data is manufactured or assumed.
    """
    terms = review_prospective_terms()
    prior = draft_gold_terms_v13()
    if (terms.sku != "MOJ-PROP-01"
            or terms.closed_trades_total != 50
            or terms.trading_days_each_phase != 6
            or terms.public_post_hours != 672
            or prior.stage_one_profit_target_pct != D("9.6")
            or prior.stage_two_profit_target_pct != D("6")
            or prior.max_profitable_day_share_pct != D("32")
            or terms.source_draft_sha256 != prior.digest_sha256):
        raise ValueError("draft policy changed; independent review required")
    if type(snapshot) is not EngineSnapshot:
        raise ValueError("immutable engine snapshot required")
    if type(snapshot.challenge_ref) is not str or REFERENCE.fullmatch(snapshot.challenge_ref) is None:
        raise ValueError("opaque challenge reference required")
    if (type(snapshot.accepted_terms_sha256) is not str
            or snapshot.accepted_terms_sha256 != terms.contract_candidate_sha256):
        raise ValueError("the exact v1.4.1 buyer contract digest is required")
    if (type(snapshot.closed_fills) is not tuple or type(snapshot.equity_marks) is not tuple
            or len(snapshot.closed_fills) + len(snapshot.equity_marks) > MAX_EVENTS):
        raise ValueError("bounded immutable closed-trade and equity snapshot required")
    start = _utc(snapshot.evaluation_started_at, "evaluation_started_at")
    now = _utc(snapshot.as_of, "as_of")
    end = start + CHALLENGE_TIME
    if now < start:
        raise ValueError("assessment cannot predate challenge start")
    accept = (_utc(snapshot.phase_one_accepted_at, "phase_one_accepted_at")
              if snapshot.phase_one_accepted_at is not None else None)
    second = (_utc(snapshot.phase_two_started_at, "phase_two_started_at")
              if snapshot.phase_two_started_at is not None else None)
    final = (_utc(snapshot.phase_two_completed_at, "phase_two_completed_at")
             if snapshot.phase_two_completed_at is not None else None)
    if any(t is not None and (t > now or not start <= t < end)
           for t in (accept, second, final)):
        raise ValueError("phase transition beyond assessment or 28-day window")
    if second is not None and (accept is None or second < accept):
        raise ValueError("phase two requires prior first-stage acceptance")
    if final is not None and (second is None or final < second):
        raise ValueError("final phase requires sequential second-stage start")
    opened = {1: start, 2: second}
    closed = {1: accept, 2: final}
    events = {}
    position_sources = {}
    position_phases = {}
    fills = {}
    equities = []
    global_reasons = []
    replays = 0
    digest_rows = []
    for event in snapshot.closed_fills:
        if type(event) is not SimulatedClosedFill:
            raise ValueError("immutable closed-fill evidence required")
        phase = _phase(event.phase)
        source = _id(event.data_source, "data_source")
        event_id = _id(event.external_event_id, "external_event_id")
        position = _id(event.external_position_id, "external_position_id")
        _evidence(event.evidence_sha256)
        if event.symbol != "XAUUSD":
            global_reasons.append("unsupported_non_xauusd_close")
        when = _utc(event.closed_at, "closed_at")
        if when > now or not start <= when < end:
            global_reasons.append("close_outside_evaluation_or_future")
        if opened[phase] is None or when < opened[phase] or (closed[phase] is not None and when > closed[phase]):
            global_reasons.append("close_outside_sequential_phase_window")
        gross = _money(event.gross_realized_usd, "gross_realized_usd")
        fee = _money(event.total_fees_usd, "total_fees_usd", nonnegative=True)
        if type(event.position_fully_closed) is not bool:
            raise ValueError("strict final position flag required")
        if event.reconciliation_status != "verified":
            global_reasons.append("unreconciled_close_event")
        key = ("fill", source, event_id)
        previous = events.get(key)
        if previous is not None:
            if previous != event:
                global_reasons.append("conflicting_duplicate_event_id")
            else:
                replays += 1
            continue
        events[key] = event
        if position in position_sources and position_sources[position] != source:
            global_reasons.append("cross_source_position_id_conflict")
        position_sources[position] = source
        ps_key = (source, position)
        if ps_key in position_phases and position_phases[ps_key] != phase:
            global_reasons.append("position_reused_between_simulated_phases")
        position_phases[ps_key] = phase
        fills.setdefault((phase, source, position), []).append((event, when, gross, fee))
        digest_rows.append(("fill", phase, source, event_id, position, event.symbol,
                            when.isoformat(), str(gross), str(fee),
                            event.position_fully_closed, event.reconciliation_status,
                            event.evidence_sha256))
    for mark in snapshot.equity_marks:
        if type(mark) is not SimulatedEquityMark:
            raise ValueError("immutable equity mark required")
        phase = _phase(mark.phase)
        source = _id(mark.data_source, "data_source")
        event_id = _id(mark.external_event_id, "external_event_id")
        _evidence(mark.evidence_sha256)
        when = _utc(mark.observed_at, "observed_at")
        if when > now or not start <= when < end:
            global_reasons.append("equity_outside_evaluation_or_future")
        if opened[phase] is None or when < opened[phase] or (closed[phase] is not None and when > closed[phase]):
            global_reasons.append("equity_outside_sequential_phase_window")
        equity = _money(mark.equity_usd, "equity_usd", nonnegative=True)
        if type(mark.is_utc_day_open) is not bool:
            raise ValueError("strict UTC day-open flag required")
        if mark.reconciliation_status != "verified":
            global_reasons.append("unreconciled_equity_observation")
        key = ("mark", source, event_id)
        previous = events.get(key)
        if previous is not None:
            if previous != mark:
                global_reasons.append("conflicting_duplicate_equity_id")
            else:
                replays += 1
            continue
        events[key] = mark
        equities.append((mark, when, equity))
        digest_rows.append(("equity", phase, source, event_id, when.isoformat(),
                            str(equity), mark.is_utc_day_open,
                            mark.reconciliation_status, mark.evidence_sha256))
    first = _phase_result(
        1, fills, equities, opened=start, ended=accept, as_of=now,
        required_net=CAPITAL * D("9.6") / 100,
    )
    stage_two_opened = second if second is not None else start
    second_stage = _phase_result(
        2, fills, equities, opened=stage_two_opened, ended=final, as_of=now,
        required_net=CAPITAL * D("6") / 100,
    )
    if second is not None and not first.mathematical_pass:
        global_reasons.append("phase_two_started_without_phase_one_mathematical_pass")
    # An event may contain several partial fills. Only one final close
    # event per stable position ID makes that POSITION countable.
    completed_all = set()
    for key, entries in fills.items():
        ordered = sorted(entries, key=lambda row: (row[1], row[0].external_event_id))
        final_flags = [i for i, row in enumerate(ordered)
                       if row[0].position_fully_closed is True]
        if len(final_flags) == 1 and final_flags[0] == len(ordered) - 1:
            completed_all.add((key[1], key[2]))
    total_positions = len(completed_all)
    if total_positions < terms.closed_trades_total:
        global_reasons.append("fewer_than_fifty_distinct_fully_closed_positions_total")
    phase_math = (first.mathematical_pass and second_stage.mathematical_pass
                  and not global_reasons)
    if social is None:
        social_ok = False
    else:
        if type(social) is not Social28DayReview:
            raise ValueError("typed independent social timing review required")
        social_ok = (social.candidate_platform in terms.social_platforms
                     and social.timeline_mathematically_consistent is True
                     and social.observed_hours >= terms.public_post_hours
                     and not social.reasons)
    combined_math = phase_math and social_ok
    blockers = list(global_reasons)
    blockers.extend(first.blockers)
    blockers.extend(second_stage.blockers)
    if not social_ok:
        blockers.append("social_post_28day_mathematical_review_pending")
    if first.risk_breached or second_stage.risk_breached:
        state = "SIMULATED_RISK_BREACHED"
    elif not phase_math and now >= end:
        state = "SIMULATED_EVALUATION_EXPIRED"
    elif phase_math and social_ok:
        state = "BOTH_MATH_REVIEWS_PASSED_EXTERNAL_PROOF_REQUIRED"
    elif phase_math:
        state = "TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK"
    elif second is not None:
        state = "SIMULATED_STAGE_TWO_IN_REVIEW"
    elif first.mathematical_pass:
        state = "SIMULATED_STAGE_ONE_MATH_PASSED_WAITING_TRANSITION"
    else:
        state = "SIMULATED_STAGE_ONE_IN_REVIEW"
    payload = dict(
        domain="mojprop.v141.simulated.event-replay.review.v1",
        challenge_ref=snapshot.challenge_ref, terms=terms.contract_candidate_sha256,
        start=start.isoformat(), now=now.isoformat(),
        first_acceptance=accept.isoformat() if accept else None,
        second_start=second.isoformat() if second else None,
        second_completion=final.isoformat() if final else None,
        records=sorted(digest_rows, key=lambda row: json.dumps(row)),
    )
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True).encode("utf-8")).hexdigest()
    return ChallengeReplayDecision(
        challenge_ref=snapshot.challenge_ref,
        contract_version=terms.version, terms_sha256=terms.contract_candidate_sha256,
        snapshot_sha256=digest, evaluation_deadline_utc=end.isoformat(),
        assessment_utc=now.isoformat(), phase_one=first, phase_two=second_stage,
        combined_unique_closed_positions=total_positions,
        replayed_duplicate_event_count=replays,
        phase_math_complete=phase_math, social_math_complete=social_ok,
        combined_math_complete=combined_math, state=state,
        blockers=tuple(dict.fromkeys(blockers)),
    )
