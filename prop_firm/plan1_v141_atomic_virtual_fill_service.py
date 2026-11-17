"""Internal-only atomic VIRTUAL fill writer — NOT a broker execution endpoint.

Requires a PRE-PROVISIONED site trader and challenge, a server-owned HMAC
feed key, an authenticated site user and a trusted upstream DEMO feed.
No signup, order-matching, price feed, wallet, live trading, checkout or payout
is created. This module is untested on real MariaDB and MUST NOT deploy until
off-host backups and an authorized concurrency/rollback rehearsal succeed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import re

from django.db import transaction

from .plan1_v141_virtual_tenant_models import (
    PropV141VirtualBook, PropV141VirtualFill,
)
from .plan1_v141_virtual_tenant_fill_ledger import (
    VirtualFill, ProvisionedVirtualChallenge, VirtualLedgerRejected,
    replay_provisioned_virtual_books, ZERO_SHA,
)
from .plan1_v14_social_or_50_terms import review_prospective_terms

_SIG = re.compile(r"[0-9a-f]{64}\Z")


class DurableVirtualFillRejected(ValueError):
    """Unknown trader, invalid feed evidence or nonmonotonic virtual ledger."""


@dataclass(frozen=True)
class StoredVirtualFillReceipt:
    challenge_ref: str
    sequence: int
    event_id: str
    history_sha256: str
    realized_net_usd: Decimal
    fully_closed_positions: int
    idempotent_replay: bool
    # A review result never proves independent feed or broker legitimacy.
    signed_raw_feed_archive_independently_verified: bool = False
    production_mariadb_rehearsal_verified: bool = False
    live_broker_orders_authorized: bool = False
    customer_fee_collection_authorized: bool = False
    payouts_authorized: bool = False


def _payload(book, fill):
    """Exact domain-separated signed bytes; cannot be moved to another book."""
    if type(fill) is not VirtualFill:
        raise DurableVirtualFillRejected("typed server-authenticated virtual fill required")
    timestamp = fill.executed_at_utc
    if (type(timestamp) is not datetime or timestamp.tzinfo is None
            or timestamp.utcoffset() is None):
        raise DurableVirtualFillRejected("trusted UTC timestamp required")
    doc = dict(
        domain="mojprop.v141.internal-virtual-fill.v1",
        book_pk=book.pk, state_pk=book.state_id,
        expected_contract=book.terms_sha256,
        owner_pk=str(book.owner_id),
        trader_ref=fill.trader_ref,
        challenge_ref=fill.challenge_ref,
        event_id=fill.event_id,
        sequence=fill.sequence,
        position_ref=fill.position_ref,
        stage=fill.stage, action=fill.action, direction=fill.direction,
        symbol=fill.symbol,
        qty=str(fill.quantity_ounces),
        price=str(fill.price_usd_per_ounce),
        fee=str(fill.fee_usd),
        event_time=timestamp.astimezone(timezone.utc).isoformat(),
        feed_source=fill.feed_source,
        source_evidence_sha256=fill.raw_event_sha256,
    )
    return json.dumps(doc, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _stored_fill(book, row):
    return VirtualFill(
        trader_ref=book.trader_ref,
        challenge_ref=book.state.challenge_ref,
        event_id=row.event_id, sequence=row.sequence,
        position_ref=row.position_ref,
        stage=row.stage, action=row.action,
        direction=row.direction, symbol=row.symbol,
        quantity_ounces=str(row.quantity_ounces),
        price_usd_per_ounce=str(row.price_usd_per_ounce),
        fee_usd=str(row.fee_usd),
        executed_at_utc=row.executed_at_utc,
        feed_source=row.feed_source,
        raw_event_sha256=row.raw_event_sha256,
    )


def _book_snapshot(book, events, *, now):
    provisioned = ProvisionedVirtualChallenge(
        trader_ref=book.trader_ref,
        challenge_ref=book.state.challenge_ref,
        terms_sha256=book.terms_sha256,
        opened_at_utc=book.evaluation_started_at,
        max_unlocked_stage=book.max_unlocked_stage,
        trusted_feed_source=book.trusted_feed_source,
    )
    return replay_provisioned_virtual_books(
        challenges=(provisioned,), events=tuple(events), server_now=now,
    ).challenge_books[0]


def _existing_row_matches(book, row, fill):
    # DB DecimalFields always reload at their fixed storage scale, whereas a
    # signed upstream payload may represent the same value with fewer zeros.
    # Compare exact numeric values but preserve signed payload verification.
    try:
        timestamp = fill.executed_at_utc.astimezone(timezone.utc)
        return all((
            row.book_id == book.pk,
            row.event_id == fill.event_id,
            row.sequence == fill.sequence,
            row.position_ref == fill.position_ref,
            row.stage == fill.stage,
            row.action == fill.action,
            row.direction == fill.direction,
            row.symbol == fill.symbol,
            row.feed_source == fill.feed_source,
            row.raw_event_sha256 == fill.raw_event_sha256,
            row.executed_at_utc.astimezone(timezone.utc) == timestamp,
            row.quantity_ounces == Decimal(str(fill.quantity_ounces)),
            row.price_usd_per_ounce == Decimal(str(fill.price_usd_per_ounce)),
            row.fee_usd == Decimal(str(fill.fee_usd)),
        ))
    except (ValueError, ArithmeticError, AttributeError, TypeError):
        return False

@transaction.atomic
def store_v141_virtual_fill(
    *, trusted_book_pk: int, authenticated_site_user_pk: int,
    fill: VirtualFill, ingress_signature_sha256: str,
    server_owned_hmac_keys: dict, server_now: datetime,
) -> StoredVirtualFillReceipt:
    """Append one internally signed DEMO event under a database row lock.

    Never pass a client-supplied book PK or 'authenticated_site_user_pk':
    these must come only from a separately authorized site middleware layer.
    """
    if (type(trusted_book_pk) is not int or trusted_book_pk <= 0
            or type(authenticated_site_user_pk) is not int
            or authenticated_site_user_pk <= 0
            or type(server_owned_hmac_keys) is not dict
            or type(server_now) is not datetime
            or server_now.tzinfo is None or server_now.utcoffset() is None):
        raise DurableVirtualFillRejected("server-owned authenticated context required")
    if (type(ingress_signature_sha256) is not str
            or _SIG.fullmatch(ingress_signature_sha256) is None):
        raise DurableVirtualFillRejected("exact source HMAC signature required")

    try:
        book = (PropV141VirtualBook.objects.select_related("owner", "state")
                .select_for_update().get(pk=trusted_book_pk))
    except PropV141VirtualBook.DoesNotExist as exc:
        raise DurableVirtualFillRejected("unprovisioned site challenge") from exc
    if (book.owner_id != authenticated_site_user_pk
            or book.owner.is_active is not True):
        raise DurableVirtualFillRejected("cross-tenant or inactive site user")
    terms = review_prospective_terms()
    if (book.terms_sha256 != terms.contract_candidate_sha256
            or book.terms_sha256 != book.state.terms_sha256
            or book.trusted_feed_source != book.state.trusted_feed_source
            or book.trader_ref != fill.trader_ref
            or book.state.challenge_ref != fill.challenge_ref):
        raise DurableVirtualFillRejected("challenge/customer terms or source mismatch")
    if (book.max_unlocked_stage == 2
            and (book.state.last_phase_one_accepted_at is None
                 or not book.state.last_phase_one_evidence_sha256)):
        raise DurableVirtualFillRejected("stage two lacks independently recorded first-stage checkpoint")
    if book.state.last_engine_state in (
            "SIMULATED_RISK_BREACHED", "SIMULATED_EVALUATION_EXPIRED",
            "TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK"):
        raise DurableVirtualFillRejected("challenge stage is not open for new virtual fills")

    key = server_owned_hmac_keys.get(book.state.trusted_key_id)
    if type(key) is not bytes or len(key) < 32:
        raise DurableVirtualFillRejected("valid private event-source key not configured")
    required_sig = hmac.new(key, _payload(book, fill), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(required_sig, ingress_signature_sha256):
        raise DurableVirtualFillRejected("internal virtual feed signature mismatch")

    rows = list(PropV141VirtualFill.objects.filter(book=book).order_by("sequence"))
    past_events = tuple(_stored_fill(book, row) for row in rows)
    try:
        before = _book_snapshot(book, past_events, now=server_now)
    except VirtualLedgerRejected as exc:
        raise DurableVirtualFillRejected("persisted virtual book failed replay") from exc
    if (type(book.last_sequence) is not int or book.last_sequence != len(rows)
            or book.last_history_sha256 != (
                before.canonical_event_history_sha256 if rows else "")
            or book.last_realized_net_usd != before.realized_net_after_all_fees_usd
            or book.last_fully_closed_count != before.fully_closed_positions_total):
        raise DurableVirtualFillRejected("stored virtual book fails immutable replay consistency")

    old = next((row for row in rows if row.event_id == fill.event_id), None)
    if old is not None:
        if not _existing_row_matches(book, old, fill):
            raise DurableVirtualFillRejected("same source event ID has conflicting content")
        return StoredVirtualFillReceipt(
            challenge_ref=book.state.challenge_ref,
            sequence=old.sequence, event_id=old.event_id,
            history_sha256=book.last_history_sha256,
            realized_net_usd=before.realized_net_after_all_fees_usd,
            fully_closed_positions=before.fully_closed_positions_total,
            idempotent_replay=True,
        )
    if type(fill.sequence) is not int or fill.sequence != book.last_sequence + 1:
        raise DurableVirtualFillRejected("noncontiguous internal source event sequence")
    if PropV141VirtualFill.objects.filter(event_id=fill.event_id).exists():
        raise DurableVirtualFillRejected("source event ID already consumed by another customer")

    try:
        result = _book_snapshot(book, past_events + (fill,), now=server_now)
    except VirtualLedgerRejected as exc:
        raise DurableVirtualFillRejected("unreconciled new virtual fill") from exc
    if result.realized_net_after_all_fees_usd.as_tuple().exponent < -8:
        raise DurableVirtualFillRejected("virtual PnL precision exceeds persistent accounting scale")
    event = PropV141VirtualFill.objects.create(
        book=book, sequence=fill.sequence,
        event_id=fill.event_id, position_ref=fill.position_ref,
        stage=fill.stage, action=fill.action,
        direction=fill.direction, symbol=fill.symbol,
        quantity_ounces=Decimal(str(fill.quantity_ounces)),
        price_usd_per_ounce=Decimal(str(fill.price_usd_per_ounce)),
        fee_usd=Decimal(str(fill.fee_usd)),
        executed_at_utc=fill.executed_at_utc,
        feed_source=fill.feed_source,
        raw_event_sha256=fill.raw_event_sha256,
    )
    book.last_sequence = fill.sequence
    book.last_history_sha256 = result.canonical_event_history_sha256
    book.last_realized_net_usd = result.realized_net_after_all_fees_usd
    book.last_fully_closed_count = result.fully_closed_positions_total
    book.save(update_fields=[
        "last_sequence", "last_history_sha256", "last_realized_net_usd",
        "last_fully_closed_count", "updated_at",
    ])
    return StoredVirtualFillReceipt(
        challenge_ref=book.state.challenge_ref,
        sequence=event.sequence, event_id=event.event_id,
        history_sha256=result.canonical_event_history_sha256,
        realized_net_usd=result.realized_net_after_all_fees_usd,
        fully_closed_positions=result.fully_closed_positions_total,
        idempotent_replay=False,
    )
