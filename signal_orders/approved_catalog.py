"""Deterministic protected-catalog fingerprint for one nonfinancial signal offer.

A valid fingerprint is only an operator configuration gate. It is NOT
independent evidence of ownership, licensing, buyer identity or rights.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json

from core.mojtaba_signal_service_contract import (
    BOT_IDENTITY, SignalOffer, SignalTenantRoute, SignalServiceKind,
    validate_route_offer_alignment,
)


def approved_offer_fingerprint(route: SignalTenantRoute, offer: SignalOffer):
    """Bind host/path/tenant/language/service/type/price/currency to one approval."""
    validate_route_offer_alignment(route, offer)
    if route.active is not True or offer.active is not True:
        raise ValueError("inactive_service_not_offerable")
    if (route.bot_identity != BOT_IDENTITY or offer.bot_identity != BOT_IDENTITY
            or not isinstance(offer.service_kind, SignalServiceKind)):
        raise ValueError("single_bot_service_required")
    payload = {
        "version": 1,
        "tenant_id": route.tenant_id,
        "canonical_host": route.canonical_host,
        "path_prefix": route.path_prefix,
        "language": route.language,
        "bot_identity": BOT_IDENTITY,
        "offer_id": offer.offer_id,
        "service_kind": offer.service_kind.value,
        "price": format(Decimal(offer.price).normalize(), "f"),
        "currency": offer.currency,
        "owner_approved": offer.owner_approved and route.owner_approved,
        "legal_reviewed": offer.legal_reviewed and route.legal_reviewed,
        "rights_cleared": offer.rights_cleared,
        "financial_calls_enabled": offer.financial_calls_enabled,
        "guaranteed_profit_promised": offer.guaranteed_profit_promised,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()
