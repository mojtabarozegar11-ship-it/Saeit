"""Durable, unique TRX quote proposals for non-financial signal services.

Internal-only API. No URL is registered. Never settle a TRX transaction or
deliver an entitlement from this module. Merchant configuration and key come
from protected Django settings, not requests or offers.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re

from django.conf import settings
from django.db import IntegrityError, transaction

from core.mojtaba_signal_tron_invoice_contract import (
    TrxQuoteError, _clock, build_trx_invoice_quote, verify_trx_invoice_quote,
)
from .models import PendingSignalOrderRecord, PendingSignalTrxQuote
from .approved_catalog import approved_offer_fingerprint
from core.mojtaba_signal_service_contract import SignalTenantRoute, SignalOffer, SignalContractError
from .service import _ID, _check_row


class DurableSignalQuoteError(ValueError):
    pass


@dataclass(frozen=True)
class DurableQuoteReceipt:
    invoice_id: str
    order_id: str
    tenant_id: str
    signed_token: str
    created: bool
    state: str = "pending_external_settlement"
    settled: bool = False
    entitlement_granted: bool = False
    delivered: bool = False


def _merchant_config(route, offer):
    if not isinstance(route, SignalTenantRoute) or not isinstance(offer, SignalOffer):
        raise DurableSignalQuoteError("protected_service_contract_required")
    try:
        fingerprint = approved_offer_fingerprint(route, offer)
    except (SignalContractError, ValueError, TypeError) as exc:
        raise DurableSignalQuoteError("approved_service_contract_invalid") from exc
    allowlist = getattr(settings, "MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS", ())
    if (type(allowlist) not in (list, tuple) or not 1 <= len(allowlist) <= 1024
            or any(type(value) is not str
                   or re.fullmatch(r"[0-9a-f]{64}", value) is None
                   for value in allowlist)
            or fingerprint not in allowlist):
        raise DurableSignalQuoteError("service_not_in_protected_approved_catalog")
    if getattr(settings, "MOJTABA_SIGNAL_TRON_QUOTE_ENABLED", False) is not True:
        raise DurableSignalQuoteError("quote_issuance_disabled")
    expected_host = getattr(settings, "MOJTABA_SIGNAL_CANONICAL_HOST", "")
    receiver = getattr(settings, "MOJTABA_SIGNAL_TRON_RECEIVER", "")
    hex_key = getattr(settings, "MOJTABA_SIGNAL_TRON_QUOTE_HMAC_KEY_HEX", "")
    if (type(expected_host) is not str or not expected_host
            or route.canonical_host != expected_host):
        raise DurableSignalQuoteError("protected_merchant_scope_missing")
    if type(receiver) is not str or not receiver:
        raise DurableSignalQuoteError("protected_receiver_missing")
    if (type(hex_key) is not str or re.fullmatch(r"[0-9a-fA-F]{64}", hex_key) is None
            or hex_key.lower() == "0" * 64):
        raise DurableSignalQuoteError("protected_quote_hmac_key_missing")
    # Compromise of one signing purpose must not silently compromise the other.
    # Buyer identity and invoice authorization use independent cryptographic keys.
    buyer_hex = getattr(settings, "MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX", "")
    if (type(buyer_hex) is str and len(buyer_hex) == 64
            and hmac.compare_digest(hex_key.lower(), buyer_hex.lower())):
        raise DurableSignalQuoteError("quote_and_buyer_signing_keys_must_differ")
    return receiver, bytes.fromhex(hex_key)


def _intact(row, pending, route, offer, *, receiver, key, now):
    # order_id is Django's integer FK; compare the natural order identifier.
    if (row.order.order_id != pending["order_id"]
            or row.order.tenant_id != pending["tenant_id"]
            or type(row.signed_token) is not str
            or not 1 <= len(row.signed_token) <= 4096
            or type(row.token_digest) is not str
            or not hmac.compare_digest(
                hashlib.sha256(row.signed_token.encode("ascii", errors="replace")).hexdigest(),
                row.token_digest,
            )):
        raise DurableSignalQuoteError("stored_quote_integrity_invalid")
    try:
        claims = verify_trx_invoice_quote(
            row.signed_token, pending, route, offer,
            trusted_receiver_address=receiver, signing_secret=key, now=now,
        )
    except TrxQuoteError as exc:
        raise DurableSignalQuoteError("stored_quote_verification_failed") from exc
    if claims["invoice_id"] != row.invoice_id:
        raise DurableSignalQuoteError("stored_quote_invoice_mismatch")
    return DurableQuoteReceipt(
        invoice_id=row.invoice_id, order_id=pending["order_id"],
        tenant_id=pending["tenant_id"], signed_token=row.signed_token,
        created=False,
    )


@transaction.atomic
def issue_pending_trx_quote(*, order_id, tenant_id, invoice_id,
                            trusted_route, trusted_offer, now=None):
    """Write once; lock order row; reject conflicting invoice IDs atomically.

    Expired quotes are not renewed automatically: a new, verified customer
    order is required, eliminating payment-to-old-invoice ambiguities.
    """
    from core.mojtaba_signal_tron_invoice_contract import _INVOICE_ID
    if (type(order_id) is not str or not _ID.fullmatch(order_id)
            or type(tenant_id) is not str or not _ID.fullmatch(tenant_id)
            or type(invoice_id) is not str or not _INVOICE_ID.fullmatch(invoice_id)):
        raise DurableSignalQuoteError("trusted_quote_identity_required")
    now = _clock(now)
    receiver, key = _merchant_config(trusted_route, trusted_offer)
    order = PendingSignalOrderRecord.objects.select_for_update().filter(
        order_id=order_id, tenant_id=tenant_id,
    ).first()
    if order is None:
        raise DurableSignalQuoteError("trusted_pending_order_not_found")
    pending = _check_row(order)
    existing = PendingSignalTrxQuote.objects.select_for_update().filter(
        order=order,
    ).first()
    if existing is not None:
        if existing.invoice_id != invoice_id:
            raise DurableSignalQuoteError("order_already_has_different_quote")
        return _intact(existing, pending, trusted_route, trusted_offer,
                       receiver=receiver, key=key, now=now)
    quote = build_trx_invoice_quote(
        pending, trusted_route, trusted_offer, invoice_id=invoice_id,
        receiver_address=receiver, trusted_receiver_address=receiver,
        signing_secret=key, now=now,
    )
    try:
        row = PendingSignalTrxQuote.objects.create(
            order=order,
            invoice_id=quote.invoice_id,
            signed_token=quote.signed_token,
            token_digest=hashlib.sha256(quote.signed_token.encode("ascii")).hexdigest(),
        )
    except IntegrityError as exc:
        raise DurableSignalQuoteError("invoice_id_already_used") from exc
    receipt = _intact(row, pending, trusted_route, trusted_offer,
                      receiver=receiver, key=key, now=now)
    return DurableQuoteReceipt(**{**receipt.__dict__, "created": True})


def read_pending_trx_quote(*, order_id, tenant_id, trusted_route,
                           trusted_offer, now=None):
    """Tenant-scoped verified read. Unregistered order and expired quote deny."""
    if (type(order_id) is not str or not _ID.fullmatch(order_id)
            or type(tenant_id) is not str or not _ID.fullmatch(tenant_id)):
        raise DurableSignalQuoteError("trusted_quote_identity_required")
    now = _clock(now)
    receiver, key = _merchant_config(trusted_route, trusted_offer)
    row = PendingSignalTrxQuote.objects.select_related("order").filter(
        order__order_id=order_id, order__tenant_id=tenant_id,
    ).first()
    if row is None:
        return None
    pending = _check_row(row.order)
    return _intact(row, pending, trusted_route, trusted_offer,
                   receiver=receiver, key=key, now=now)
