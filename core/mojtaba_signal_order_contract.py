"""Tenant-isolated pending order contract for non-financial signal services.

This is the integration boundary between the single-identity signal catalog and
an order ledger. It validates an order intent but never charges, settles,
publishes a signal or grants entitlement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

try:
    from .mojtaba_signal_service_contract import (
        BOT_IDENTITY, SignalContractError, SignalOffer, SignalTenantRoute,
        validate_route_offer_alignment,
    )
except ImportError as exc:
    if __package__:
        raise
    from mojtaba_signal_service_contract import (
        BOT_IDENTITY, SignalContractError, SignalOffer, SignalTenantRoute,
        validate_route_offer_alignment,
    )


class SignalOrderContractError(ValueError):
    pass


_ALLOWED_STATES = frozenset({"unpaid", "pending_external_settlement"})
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class SignalOrderIntent:
    order_id: str
    tenant_id: str
    offer_id: str
    bot_identity: str
    language: str
    price: Decimal
    currency: str
    customer_ref_digest: str
    requested_at: str
    state: str = "unpaid"


def _id(value, field):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise SignalOrderContractError(f"{field}_invalid")
    return value


def _timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SignalOrderContractError("requested_at_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SignalOrderContractError("requested_at_invalid") from exc
    if parsed.utcoffset() != timedelta(0):
        raise SignalOrderContractError("requested_at_invalid")
    return parsed


def validate_order_intent(
    intent: SignalOrderIntent,
    route: SignalTenantRoute,
    offer: SignalOffer,
    *,
    now=None,
) -> None:
    if not isinstance(intent, SignalOrderIntent):
        raise SignalOrderContractError("order_intent_required")
    validate_route_offer_alignment(route, offer)
    if not route.active:
        raise SignalOrderContractError("route_not_active")
    if not offer.active:
        raise SignalOrderContractError("offer_not_active")
    if intent.bot_identity != BOT_IDENTITY:
        raise SignalOrderContractError("independent_bot_identity_prohibited")
    if intent.tenant_id != route.tenant_id or intent.tenant_id != offer.tenant_id:
        raise SignalOrderContractError("order_tenant_mismatch")
    if intent.offer_id != offer.offer_id:
        raise SignalOrderContractError("order_offer_mismatch")
    if intent.language != route.language or intent.language != offer.language:
        raise SignalOrderContractError("order_language_mismatch")
    _id(intent.order_id, "order_id")
    if not isinstance(intent.price, Decimal) or not intent.price.is_finite():
        raise SignalOrderContractError("order_price_must_be_decimal")
    if intent.price != offer.price:
        raise SignalOrderContractError("order_price_mismatch")
    if intent.currency != offer.currency:
        raise SignalOrderContractError("order_currency_mismatch")
    if not isinstance(intent.customer_ref_digest, str) or not _DIGEST.fullmatch(
        intent.customer_ref_digest
    ):
        raise SignalOrderContractError("customer_ref_digest_invalid")
    requested = _timestamp(intent.requested_at)
    if now is not None:
        if now.tzinfo is None:
            raise SignalOrderContractError("order_clock_must_be_timezone_aware")
        if requested > now.astimezone(timezone.utc) + timedelta(seconds=30):
            raise SignalOrderContractError("order_requested_in_future")
    if intent.state not in _ALLOWED_STATES:
        raise SignalOrderContractError("settlement_required_before_paid_state")


def build_pending_order_record(
    intent: SignalOrderIntent,
    route: SignalTenantRoute,
    offer: SignalOffer,
    *,
    now=None,
) -> dict:
    """Return a ledger-safe pending record; this function has no side effects."""
    validate_order_intent(intent, route, offer, now=now)
    return {
        "order_id": intent.order_id,
        "tenant_id": intent.tenant_id,
        "offer_id": intent.offer_id,
        "bot_identity": BOT_IDENTITY,
        "language": intent.language,
        "price": str(intent.price),
        "currency": intent.currency,
        "customer_ref_digest": intent.customer_ref_digest,
        "state": "awaiting_external_settlement",
        "payment_required": True,
        "entitlement_granted": False,
        "financial_signal": False,
    }


def validate_order_batch(intents) -> tuple[SignalOrderIntent, ...]:
    if not isinstance(intents, (list, tuple)):
        raise SignalOrderContractError("order_batch_required")
    seen = set()
    normalized = []
    for intent in intents:
        _id(intent.order_id, "order_id")
        if intent.order_id in seen:
            raise SignalOrderContractError("duplicate_order_id")
        seen.add(intent.order_id)
        normalized.append(intent)
    return tuple(normalized)
