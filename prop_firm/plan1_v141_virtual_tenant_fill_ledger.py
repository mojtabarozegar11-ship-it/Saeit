"""Strict pure multi-tenant VIRTUAL XAUUSD fill ledger for MOJ-PROP-01.

This is deterministic accounting over a server-verified candidate event stream,
NOT a brokerage bridge, client order endpoint, enrollment, source of reliable
market quotes, or proof of execution. No money and no real orders are moved.

- Unique challenge belongs to exactly one trader, and a recorded contract SHA.
- Exact immutable per-challenge sequences and globally unique source event IDs.
- Long/short and partial close with exact ounce/price/fee arithmetic.
- One position ID can only represent one side/stage and cannot be reopened.
- Order fees are charged once; stage profit cannot be shared across customers.
- Does not calculate UNREALIZED equity/drawdown or certify stage pass: a fully
  authenticated equity/feed record is separately necessary for that decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

from .plan1_v14_social_or_50_terms import review_prospective_terms

D = Decimal
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
WINDOW = timedelta(days=28)
MAX_CHALLENGES = 5000
MAX_EVENTS = 100_000
MAX_QTY = D("1000")
MAX_PRICE = D("1000000")
MAX_FEES = D("10000")
START_BALANCE = D("100")
ZERO_SHA = "0" * 64


class VirtualLedgerRejected(ValueError):
    """The proposed isolated DEMO ledger is inconsistent or unauthenticated."""


def _id(x, field):
    if type(x) is not str or _ID.fullmatch(x) is None:
        raise VirtualLedgerRejected(field + ": bounded opaque identifier required")
    return x


def _sha(x, field):
    if type(x) is not str or _SHA.fullmatch(x) is None or x == ZERO_SHA:
        raise VirtualLedgerRejected(field + ": nonzero 64-character SHA256 required")
    return x


def _utc(x, field):
    if type(x) is not datetime or x.tzinfo is None or x.utcoffset() is None:
        raise VirtualLedgerRejected(field + ": timezone-aware datetime required")
    return x.astimezone(timezone.utc)


def _dec(x, field, *, ceiling, strictly_positive=False):
    if type(x) not in (str, int, Decimal):
        raise VirtualLedgerRejected(field + ": exact decimal, not float required")
    try:
        v = D(str(x))
    except (ValueError, InvalidOperation) as exc:
        raise VirtualLedgerRejected(field + ": invalid decimal") from exc
    if (not v.is_finite() or v < 0 or v > ceiling
            or (strictly_positive and v == 0) or v.as_tuple().exponent < -4):
        raise VirtualLedgerRejected(field + ": bounded nonnegative four-decimal number required")
    # Always normalize the same numeric value to a fixed ledger scale.
    # Django DecimalField reloads 1 as 1.0000; the audit hash MUST NOT drift.
    return v.quantize(D("0.0001"))


@dataclass(frozen=True)
class ProvisionedVirtualChallenge:
    trader_ref: str
    challenge_ref: str
    terms_sha256: str
    opened_at_utc: datetime
    # This is a server-sourced review input, NOT an authenticated approval.
    max_unlocked_stage: int
    trusted_feed_source: str
    # Stage transitions originate in PropV141SimState. The contractual
    # 28-day evaluation window covers BOTH sequential phases, not each phase.
    stage_one_accepted_at_utc: datetime | None = None
    phase_two_started_at_utc: datetime | None = None


@dataclass(frozen=True)
class VirtualFill:
    trader_ref: str
    challenge_ref: str
    event_id: str
    sequence: int
    position_ref: str
    stage: int
    action: str  # OPEN or CLOSE
    direction: str  # BUY or SELL; same side for closing an existing position
    symbol: str
    quantity_ounces: str
    price_usd_per_ounce: str
    fee_usd: str
    executed_at_utc: datetime
    feed_source: str
    raw_event_sha256: str


@dataclass(frozen=True)
class OpenVirtualPosition:
    position_ref: str
    stage: int
    direction: str
    remaining_ounces: Decimal
    weighted_open_price_usd: Decimal


@dataclass(frozen=True)
class VirtualChallengeBook:
    trader_ref: str
    challenge_ref: str
    observed_event_count: int
    unique_event_count: int
    idempotent_duplicate_count: int
    total_fees_usd: Decimal
    closed_realized_gross_usd: Decimal
    realized_net_after_all_fees_usd: Decimal
    cash_balance_excluding_unrealized_usd: Decimal
    fully_closed_positions_total: int
    fully_closed_positions_stage_one: int
    fully_closed_positions_stage_two: int
    open_positions: tuple[OpenVirtualPosition, ...]
    canonical_event_history_sha256: str
    # No mathematical tally can prove external authenticity or legal status.
    externally_authenticated_simulator_feed: bool = False
    independently_verified_live_quotes: bool = False
    floating_equity_and_risk_verified: bool = False
    challenge_pass_authorized: bool = False
    broker_orders_authorized: bool = False
    paid_enrollment_authorized: bool = False
    payouts_authorized: bool = False


@dataclass(frozen=True)
class MultiTenantVirtualReview:
    challenge_books: tuple[VirtualChallengeBook, ...]
    distinct_traders: int
    distinct_challenges: int
    total_unique_events: int
    accepted_duplicate_replays: int
    # Every event remains explicitly virtual; there is no broker account ID.
    company_real_broker_orders_emitted: int = 0
    commercial_service_enabled: bool = False


def replay_provisioned_virtual_books(
    *, challenges: tuple[ProvisionedVirtualChallenge, ...],
    events: tuple[VirtualFill, ...],
    server_now: datetime,
) -> MultiTenantVirtualReview:
    """Replay ONLY events already authenticated/authorized upstream.

    Authorization cannot be inferred here, even if a caller fabricates
    feed names or evidence hashes. The caller must independently establish
    authenticated user permissions and immutable source evidence.
    """
    if (type(challenges) is not tuple or type(events) is not tuple
            or len(challenges) > MAX_CHALLENGES or len(events) > MAX_EVENTS):
        raise VirtualLedgerRejected("bounded immutable challenge/event tuples required")
    now = _utc(server_now, "server_now")
    contract = review_prospective_terms().contract_candidate_sha256
    registry = {}
    for c in challenges:
        if type(c) is not ProvisionedVirtualChallenge:
            raise VirtualLedgerRejected("typed privately provisioned challenges required")
        trader = _id(c.trader_ref, "trader_ref")
        ref = _id(c.challenge_ref, "challenge_ref")
        _sha(c.terms_sha256, "terms_sha256")
        _id(c.trusted_feed_source, "trusted_feed_source")
        start = _utc(c.opened_at_utc, "opened_at_utc")
        if (ref in registry or c.terms_sha256 != contract
                or start > now or type(c.max_unlocked_stage) is not int
                or c.max_unlocked_stage not in (1, 2)):
            raise VirtualLedgerRejected("duplicate, premature, wrong-version or invalid provisioned challenge")
        accepted = (None if c.stage_one_accepted_at_utc is None else
                    _utc(c.stage_one_accepted_at_utc, "stage_one_accepted_at_utc"))
        second = (None if c.phase_two_started_at_utc is None else
                  _utc(c.phase_two_started_at_utc, "phase_two_started_at_utc"))
        if accepted is not None and (
                accepted < start or accepted > now or accepted >= start + WINDOW):
            raise VirtualLedgerRejected("stage-one acceptance outside its own 28-day window")
        if c.max_unlocked_stage == 1 and second is not None:
            raise VirtualLedgerRejected("stage two has not been unlocked")
        if c.max_unlocked_stage == 2 and (
                accepted is None or second is None
                or not accepted <= second <= now
                or second >= start + WINDOW):
            raise VirtualLedgerRejected("stage two requires an accepted first stage and trusted start")
        registry[ref] = (c, trader, start, accepted, second)

    # Event IDs are globally scoped by the server's feed across all tenants,
    # preventing one upstream fill from being credited to two challenge books.
    seen_global_ids = {}
    by_challenge = {ref: {} for ref in registry}
    duplicates = {ref: 0 for ref in registry}
    for e in events:
        if type(e) is not VirtualFill:
            raise VirtualLedgerRejected("typed immutable virtual fill required")
        trader = _id(e.trader_ref, "fill.trader_ref")
        ref = _id(e.challenge_ref, "fill.challenge_ref")
        event_id = _id(e.event_id, "fill.event_id")
        pos_id = _id(e.position_ref, "fill.position_ref")
        source = _id(e.feed_source, "fill.feed_source")
        _sha(e.raw_event_sha256, "raw_event_sha256")
        if ref not in registry:
            raise VirtualLedgerRejected("event challenge not privately provisioned")
        c, expected_trader, start, accepted, second = registry[ref]
        if trader != expected_trader or source != c.trusted_feed_source:
            raise VirtualLedgerRejected("cross-tenant or foreign-source virtual fill")
        if (type(e.sequence) is not int or not 1 <= e.sequence <= MAX_EVENTS
                or type(e.stage) is not int or e.stage not in (1, 2)
                or e.stage > c.max_unlocked_stage):
            raise VirtualLedgerRejected("invalid sequence or locked stage")
        if e.action not in ("OPEN", "CLOSE") or e.direction not in ("BUY", "SELL") or e.symbol != "XAUUSD":
            raise VirtualLedgerRejected("only XAUUSD OPEN/CLOSE BUY/SELL virtual fills allowed")
        when = _utc(e.executed_at_utc, "executed_at_utc")
        phase_start = start if e.stage == 1 else second
        # One legal 28-day evaluation clock for both phases. The second-phase
        # transition cannot restart, extend or bypass the original deadline.
        if (phase_start is None or not phase_start <= when <= now
                or when >= start + WINDOW):
            raise VirtualLedgerRejected("virtual fill outside shared 28-day evaluation window")
        # An already-recorded final fill may share the acceptance timestamp.
        # Writer still forbids appending ANY new stage-one event after acceptance.
        if e.stage == 1 and accepted is not None and when > accepted:
            raise VirtualLedgerRejected("stage-one fill after authoritative stage acceptance")
        qty = _dec(e.quantity_ounces, "quantity_ounces", ceiling=MAX_QTY, strictly_positive=True)
        price = _dec(e.price_usd_per_ounce, "price_usd_per_ounce", ceiling=MAX_PRICE, strictly_positive=True)
        fee = _dec(e.fee_usd, "fee_usd", ceiling=MAX_FEES)
        prev = seen_global_ids.get(event_id)
        if prev is not None:
            if prev != e:
                raise VirtualLedgerRejected("global source event reused or changed across challenge books")
            duplicates[ref] += 1
            continue
        seen_global_ids[event_id] = e
        if e.sequence in by_challenge[ref]:
            raise VirtualLedgerRejected("duplicate per-challenge event sequence")
        by_challenge[ref][e.sequence] = (e, when, qty, price, fee, pos_id)

    books = []
    total = 0
    for ref, (c, trader, _start, _accepted, _second) in sorted(registry.items()):
        candidates = by_challenge[ref]
        numbers = sorted(candidates)
        if numbers != list(range(1, len(numbers) + 1)):
            raise VirtualLedgerRejected("gap or out-of-order per-challenge event sequence")
        positions = {}
        finalized = set()
        total_fee = D("0")
        gross = D("0")
        full_counts = {1: 0, 2: 0}
        last_time = None
        history = ZERO_SHA
        for seq in numbers:
            e, when, qty, price, fee, pos_id = candidates[seq]
            if last_time is not None and when < last_time:
                raise VirtualLedgerRejected("sequence moves backwards in virtual execution time")
            last_time = when
            key = pos_id
            if e.action == "OPEN":
                if key in finalized:
                    raise VirtualLedgerRejected("closed virtual position ID cannot be reopened")
                if key in positions:
                    stage, direction, lots = positions[key]
                    if stage != e.stage or direction != e.direction:
                        raise VirtualLedgerRejected("virtual position changes stage or side")
                    if sum((v for v, _ in lots), D("0")) + qty > MAX_QTY:
                        raise VirtualLedgerRejected("virtual position size limit exceeded")
                    lots.append((qty, price))
                else:
                    positions[key] = (e.stage, e.direction, [(qty, price)])
            else:
                if key not in positions:
                    raise VirtualLedgerRejected("virtual close without an existing open position")
                stage, side, lots = positions[key]
                remaining = sum((v for v, _ in lots), D("0"))
                if stage != e.stage or side != e.direction or qty > remaining:
                    raise VirtualLedgerRejected("wrong stage/side or excessive partial virtual close")
                # FIFO lots avoid repeating weighted-average decimals and
                # preserve exact 8-place P&L from 4-place price and quantity.
                amount_left = qty
                next_lots = []
                sign = D("1") if side == "BUY" else D("-1")
                for lot_qty, lot_price in lots:
                    consumed = min(amount_left, lot_qty)
                    gross += (price - lot_price) * consumed * sign
                    amount_left -= consumed
                    if consumed < lot_qty:
                        next_lots.append((lot_qty - consumed, lot_price))
                if amount_left != 0:
                    raise VirtualLedgerRejected("virtual FIFO position accounting mismatch")
                if next_lots:
                    positions[key] = (stage, side, next_lots)
                else:
                    del positions[key]
                    finalized.add(key)
                    full_counts[stage] += 1
            total_fee += fee
            row = dict(
                contract=c.terms_sha256,
                trader=trader, challenge=ref,
                event_id=e.event_id, sequence=seq, position=pos_id,
                phase=e.stage, action=e.action, side=e.direction,
                symbol=e.symbol, qty=str(qty), price=str(price), fee=str(fee),
                when=when.isoformat(), feed=e.feed_source, evidence=e.raw_event_sha256,
                predecessor=history,
            )
            history = sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=True).encode("utf-8")).hexdigest()
        # A finalized first stage must not carry open inventory into stage two.
        if c.max_unlocked_stage == 2 and any(
                position_stage == 1
                for position_stage, _side, _lots in positions.values()):
            raise VirtualLedgerRejected("open first-stage inventory cannot migrate to stage two")
        open_positions = tuple(
            OpenVirtualPosition(
                position_ref=position, stage=stage, direction=direction,
                remaining_ounces=sum((v for v, _ in lots), D("0")),
                weighted_open_price_usd=(
                    sum((v * px for v, px in lots), D("0"))
                    / sum((v for v, _ in lots), D("0"))
                ).quantize(D("0.00000001")),
            )
            for position, (stage, direction, lots) in sorted(positions.items())
        )
        books.append(VirtualChallengeBook(
            trader_ref=trader, challenge_ref=ref,
            observed_event_count=len(candidates) + duplicates[ref],
            unique_event_count=len(candidates),
            idempotent_duplicate_count=duplicates[ref],
            total_fees_usd=total_fee,
            closed_realized_gross_usd=gross,
            realized_net_after_all_fees_usd=gross - total_fee,
            cash_balance_excluding_unrealized_usd=START_BALANCE + gross - total_fee,
            fully_closed_positions_total=len(finalized),
            fully_closed_positions_stage_one=full_counts[1],
            fully_closed_positions_stage_two=full_counts[2],
            open_positions=open_positions,
            canonical_event_history_sha256=history,
        ))
        total += len(candidates)

    return MultiTenantVirtualReview(
        challenge_books=tuple(books),
        distinct_traders=len({c.trader_ref for c in challenges}),
        distinct_challenges=len(books),
        total_unique_events=total,
        accepted_duplicate_replays=sum(duplicates.values()),
    )
