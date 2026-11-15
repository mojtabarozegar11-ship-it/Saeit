"""Atomic guest email -> pending service order -> signed TRON quote proposal.

This INTERNAL flow does not send email, charge a customer, settle TRON, publish
financial signals, create delivered entitlements or register public URLs.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import re

from django.conf import settings
from django.db import transaction

from core.mojtaba_signal_order_contract import (
    SignalOrderIntent, build_pending_order_record,
)
from core.mojtaba_signal_tron_invoice_contract import _clock, _time_string
from core.mojtaba_signal_service_contract import BOT_IDENTITY

from .buyer_identity import buyer_ref_digest
from .quote_service import issue_pending_trx_quote
from .service import _ID, persist_pending_order, read_pending_order


class SignalPurchaseProposalError(ValueError):
    pass


@dataclass(frozen=True)
class SignalGuestPurchaseProposal:
    order_id: str
    invoice_id: str
    tenant_id: str
    signed_quote: str
    order_created: bool
    quote_created: bool
    payment_confirmed: bool = False
    email_sent: bool = False
    delivered: bool = False
    entitlement_granted: bool = False
    state: str = "pending_external_settlement"


def _buyer_secret():
    raw = getattr(settings, "MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX", "")
    if (type(raw) is not str or re.fullmatch(r"[0-9a-fA-F]{64}", raw) is None
            or raw.lower() == "0" * 64):
        raise SignalPurchaseProposalError("protected_guest_buyer_hmac_key_required")
    return bytes.fromhex(raw)


def _invoice_id(tenant_id, order_id):
    # Deterministic idempotency key. The actual amount, recipient and scope are
    # signed separately, and invoice uniqueness is enforced by the database.
    value = (tenant_id + "\x00" + order_id).encode("ascii")
    return "sinv-" + hashlib.sha256(value).hexdigest()[:48]


@transaction.atomic
def start_guest_nonfinancial_signal_purchase(
    *, buyer_email, order_id, trusted_route, trusted_offer, now=None,
):
    """Create no partial pending order if quote issuance is disabled or fails."""
    now = _clock(now)
    if type(order_id) is not str or not _ID.fullmatch(order_id):
        raise SignalPurchaseProposalError("trusted_order_id_required")
    if (trusted_route is None or trusted_offer is None
            or not hasattr(trusted_route, "tenant_id")):
        raise SignalPurchaseProposalError("trusted_catalog_required")
    tenant_id = trusted_route.tenant_id
    customer_digest = buyer_ref_digest(
        buyer_email=buyer_email, tenant_id=tenant_id, secret=_buyer_secret(),
    )
    previous = read_pending_order(order_id=order_id, tenant_id=tenant_id)
    requested_at = (
        previous["requested_at"] if previous is not None
        else _time_string(now)
    )
    intent = SignalOrderIntent(
        order_id=order_id,
        tenant_id=tenant_id,
        offer_id=trusted_offer.offer_id,
        bot_identity=BOT_IDENTITY,
        language=trusted_route.language,
        price=Decimal(str(trusted_offer.price)),
        currency=trusted_offer.currency,
        customer_ref_digest=customer_digest,
        requested_at=requested_at,
    )
    # Reject cross-tenant, changed customer, price, language, bot or offer.
    validated = build_pending_order_record(
        intent, trusted_route, trusted_offer, now=now,
    )
    if previous is not None and previous != validated:
        raise SignalPurchaseProposalError("existing_order_identity_or_offer_changed")
    order = persist_pending_order(
        intent, trusted_route, trusted_offer, now=now,
    )
    quote = issue_pending_trx_quote(
        order_id=order_id, tenant_id=tenant_id,
        invoice_id=_invoice_id(tenant_id, order_id),
        trusted_route=trusted_route, trusted_offer=trusted_offer,
        now=now,
    )
    return SignalGuestPurchaseProposal(
        order_id=order.order_id,
        invoice_id=quote.invoice_id,
        tenant_id=tenant_id,
        signed_quote=quote.signed_token,
        order_created=order.created,
        quote_created=quote.created,
    )
