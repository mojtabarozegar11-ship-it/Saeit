"""Fail-closed TRX quote contract for licensed non-financial Mojtaba.bot.ai offers.

This boundary produces a signed, short-lived invoice PROPOSAL. It never
creates a chain transaction, charges a wallet, marks revenue collected,
delivers content or grants access. An independently reconciled settlement
adapter and durable invoice registry are REQUIRED before paid operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import base64
import hashlib
import hmac
import json
import re

from .mojtaba_signal_order_contract import (
    SignalOrderIntent, SignalOrderContractError, build_pending_order_record,
)
from .mojtaba_signal_service_contract import (
    BOT_IDENTITY, SignalOffer, SignalTenantRoute,
)

_NETWORK = "tron-mainnet"
_ASSET = "TRX"
_SUN = Decimal("1000000")
_MAX_QUOTE_BYTES = 4096
_MAX_AGE_SECONDS = 900
_INVOICE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{5,63}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_FIELDS = frozenset({
    "invoice_id", "order_id", "tenant_id", "offer_id", "canonical_host",
    "path_prefix", "customer_ref_digest", "bot_identity", "currency",
    "amount_sun", "receiver_address", "issued_at", "expires_at",
    "network", "state",
})


class TrxQuoteError(ValueError):
    """A quoted invoice is unsafe, malformed or not independently trusted."""


@dataclass(frozen=True)
class TrxQuote:
    invoice_id: str
    order_id: str
    amount_sun: int
    receiver_address: str
    expires_at: str
    signed_token: str
    state: str = "pending_external_settlement"
    payment_collected: bool = False
    entitlement_granted: bool = False


def _clock(now):
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise TrxQuoteError("server_clock_must_be_timezone_aware")
    return now.astimezone(timezone.utc)


def _secret(secret):
    # Must be injected from protected server config, never from request data.
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise TrxQuoteError("protected_signing_secret_required")
    return secret


def _address(value):
    """Validate Tron mainnet Base58Check; a length/prefix-only test is unsafe."""
    if type(value) is not str or len(value) != 34 or any(c not in _BASE58 for c in value):
        raise TrxQuoteError("tron_mainnet_receiver_invalid")
    num = 0
    for c in value:
        num = num * 58 + _BASE58.index(c)
    raw = num.to_bytes((num.bit_length() + 7) // 8, "big")
    raw = b"\x00" * (len(value) - len(value.lstrip("1"))) + raw
    if len(raw) != 25 or raw[0] != 0x41:
        raise TrxQuoteError("tron_mainnet_receiver_invalid")
    digest = hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4]
    if not hmac.compare_digest(digest, raw[21:]):
        raise TrxQuoteError("tron_receiver_checksum_invalid")
    return value


def _amount_from_order(pending_order, route, offer, now):
    if type(pending_order) is not dict:
        raise TrxQuoteError("canonical_pending_order_required")
    if not isinstance(route, SignalTenantRoute) or not isinstance(offer, SignalOffer):
        raise TrxQuoteError("canonical_signal_contract_required")
    # Re-validate every material field against the published offer and route.
    # Do not trust a browser-submitted pending record or "paid" flags.
    try:
        price = Decimal(pending_order["price"])
        intent = SignalOrderIntent(
            order_id=pending_order["order_id"],
            tenant_id=pending_order["tenant_id"],
            offer_id=pending_order["offer_id"],
            bot_identity=pending_order["bot_identity"],
            language=pending_order["language"],
            price=price,
            currency=pending_order["currency"],
            customer_ref_digest=pending_order["customer_ref_digest"],
            requested_at=pending_order["requested_at"],
        )
        canonical = build_pending_order_record(intent, route, offer, now=now)
    except (KeyError, TypeError, ValueError, InvalidOperation, SignalOrderContractError) as exc:
        raise TrxQuoteError("pending_order_contract_invalid") from exc
    if canonical != pending_order:
        raise TrxQuoteError("pending_order_not_canonical")
    if pending_order["currency"] != _ASSET:
        raise TrxQuoteError("tron_only_quote_no_fx")
    amount = price * _SUN
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise TrxQuoteError("sun_amount_requires_exact_integer")
    if not 1 <= amount <= 10**15:
        raise TrxQuoteError("sun_amount_out_of_bounds")
    return int(amount)


def _time_string(now):
    return now.isoformat(timespec="seconds").replace("+00:00", "Z")


def _b64e(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64d(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise TrxQuoteError("signed_invoice_token_malformed")
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise TrxQuoteError("signed_invoice_token_malformed") from exc


def _payload_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _signature(payload_bytes, key):
    return hmac.new(key, payload_bytes, hashlib.sha256).digest()


def build_trx_invoice_quote(
    pending_order: dict, route: SignalTenantRoute, offer: SignalOffer, *,
    invoice_id: str, receiver_address: str, trusted_receiver_address: str,
    signing_secret: bytes, now=None, lifetime_seconds: int = 600,
) -> TrxQuote:
    """Sign a proposed invoice after validating all order and merchant inputs."""
    now = _clock(now)
    key = _secret(signing_secret)
    if type(invoice_id) is not str or not _INVOICE_ID.fullmatch(invoice_id):
        raise TrxQuoteError("invoice_id_invalid")
    if type(lifetime_seconds) is not int or not 60 <= lifetime_seconds <= _MAX_AGE_SECONDS:
        raise TrxQuoteError("quote_lifetime_invalid")
    receiver = _address(receiver_address)
    trusted = _address(trusted_receiver_address)
    if not hmac.compare_digest(receiver, trusted):
        raise TrxQuoteError("receiver_not_in_protected_registry")
    amount = _amount_from_order(pending_order, route, offer, now)
    payload = {
        "invoice_id": invoice_id,
        "order_id": pending_order["order_id"],
        "tenant_id": pending_order["tenant_id"],
        "offer_id": pending_order["offer_id"],
        "canonical_host": pending_order["canonical_host"],
        "path_prefix": pending_order["path_prefix"],
        "customer_ref_digest": pending_order["customer_ref_digest"],
        "bot_identity": BOT_IDENTITY,
        "currency": _ASSET,
        "amount_sun": amount,
        "receiver_address": receiver,
        "issued_at": _time_string(now),
        "expires_at": _time_string(now + timedelta(seconds=lifetime_seconds)),
        "network": _NETWORK,
        "state": "pending_external_settlement",
    }
    encoded = _payload_bytes(payload)
    token = _b64e(encoded) + "." + _b64e(_signature(encoded, key))
    if len(token) > _MAX_QUOTE_BYTES:
        raise TrxQuoteError("quote_token_too_large")
    return TrxQuote(
        invoice_id=invoice_id, order_id=payload["order_id"],
        amount_sun=amount, receiver_address=receiver,
        expires_at=payload["expires_at"], signed_token=token,
    )


def verify_trx_invoice_quote(
    token: str, pending_order: dict, route: SignalTenantRoute,
    offer: SignalOffer, *, trusted_receiver_address: str,
    signing_secret: bytes, now=None,
) -> dict:
    """Verify signature, exact scope, chain receiver, amount and expiry.

    Returned claims are for reconciliation only, NEVER proof of paid status.
    """
    now = _clock(now)
    key = _secret(signing_secret)
    if type(token) is not str or len(token) > _MAX_QUOTE_BYTES or token.count(".") != 1:
        raise TrxQuoteError("signed_invoice_token_malformed")
    encoded, encoded_sig = token.split(".")
    body = _b64d(encoded)
    sig = _b64d(encoded_sig)
    if len(body) > 3000 or len(sig) != 32 or not hmac.compare_digest(_signature(body, key), sig):
        raise TrxQuoteError("signed_invoice_signature_invalid")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise TrxQuoteError("signed_invoice_payload_invalid") from exc
    if type(payload) is not dict or set(payload) != _FIELDS or _payload_bytes(payload) != body:
        raise TrxQuoteError("signed_invoice_payload_invalid")
    if type(payload["invoice_id"]) is not str or not _INVOICE_ID.fullmatch(payload["invoice_id"]):
        raise TrxQuoteError("invoice_id_invalid")
    if payload["state"] != "pending_external_settlement":
        raise TrxQuoteError("paid_state_prohibited")
    if payload["currency"] != _ASSET or payload["network"] != _NETWORK:
        raise TrxQuoteError("tron_only_quote_no_fx")
    receiver = _address(payload["receiver_address"])
    trusted = _address(trusted_receiver_address)
    if not hmac.compare_digest(receiver, trusted):
        raise TrxQuoteError("receiver_not_in_protected_registry")
    amount = _amount_from_order(pending_order, route, offer, now)
    for claim in ("order_id", "tenant_id", "offer_id", "canonical_host", "path_prefix", "customer_ref_digest"):
        if payload[claim] != pending_order[claim]:
            raise TrxQuoteError("quote_scope_mismatch")
    if payload["bot_identity"] != BOT_IDENTITY:
        raise TrxQuoteError("independent_bot_identity_prohibited")
    if type(payload["amount_sun"]) is not int or payload["amount_sun"] != amount:
        raise TrxQuoteError("quote_price_mismatch")
    try:
        issued = datetime.strptime(payload["issued_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        expires = datetime.strptime(payload["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError) as exc:
        raise TrxQuoteError("quote_clock_invalid") from exc
    if issued > now + timedelta(seconds=30):
        raise TrxQuoteError("quote_issued_in_future")
    if not timedelta(seconds=60) <= expires - issued <= timedelta(seconds=_MAX_AGE_SECONDS):
        raise TrxQuoteError("quote_lifetime_invalid")
    if now >= expires:
        raise TrxQuoteError("quote_expired")
    return dict(payload)
