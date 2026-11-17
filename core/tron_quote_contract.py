"""Deterministic native TRX price quote for one approved tenant and one order.

No wallet, invoice, ledger, purchase, RPC, cash collection or fee transfer.
Source keys and trusted USD/TRX observations must be server-owned. A signed
quote is NOT proof of finality, merchant authority or an on-chain transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from hashlib import sha256
import hmac
import json
import re

from .tron_tenant_policy import TenantDecision, registered_scope

ORDER_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{7,95}\Z")
SKU_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{1,119}\Z")
SUN = Decimal("1000000")
MAX_SUN = 10**15
MAX_RATE_AGE = timedelta(minutes=5)
MAX_QUOTE_LIFETIME = timedelta(minutes=10)


class NativeTrxQuoteError(ValueError):
    pass


@dataclass(frozen=True)
class NativeTrxQuote:
    host: str
    brand: str
    tenant_id: str
    order_id: str
    sku: str
    usd_price: str
    trx_usd_rate: str
    exact_amount_sun: int
    observed_at_utc: str
    expires_at_utc: str
    signature: str


def _amount(value, name):
    if type(value) not in (str, int, Decimal):
        raise NativeTrxQuoteError(name + "_type")
    try:
        amount = Decimal(str(value))
    except (ValueError, InvalidOperation, ArithmeticError):
        raise NativeTrxQuoteError(name + "_invalid") from None
    if not amount.is_finite() or amount <= 0 or amount.adjusted() > 12:
        raise NativeTrxQuoteError(name + "_range")
    return amount


def _utc(value, name):
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise NativeTrxQuoteError(name + "_not_utc")
    return value


def _key(value):
    if type(value) is not bytes or len(value) < 32:
        raise NativeTrxQuoteError("quote_signing_key_unavailable")
    return value


def _message(quote):
    return json.dumps({
        "format": "moj.trx.native.quote.v1",
        "host": quote.host, "brand": quote.brand, "tenant": quote.tenant_id,
        "order": quote.order_id, "sku": quote.sku,
        "usd": quote.usd_price, "trx_usd": quote.trx_usd_rate,
        "sun": quote.exact_amount_sun,
        "rate_at": quote.observed_at_utc, "expires": quote.expires_at_utc,
    }, sort_keys=True, separators=(",", ":")).encode("ascii")


def _order_is_authoritative(order_id, tenant_id, sku, amount_usd,
                            order_registry, as_of_utc):
    """Quote prices must match an unpaid order from the protected DB snapshot."""
    if type(order_registry) is not dict:
        return False
    record = order_registry.get(order_id)
    if type(record) is not dict:
        return False
    if (record.get("tenant_id") != tenant_id
            or record.get("sku") != sku
            or record.get("payment_state") != "pending"
            or record.get("cancelled") is not False):
        return False
    # An unexpired, server-dated ORDER is mandatory; a 'pending' status
    # alone cannot keep an abandoned payment instruction payable forever.
    try:
        deadline = record.get("expires_at_utc")
        _utc(as_of_utc, "server_clock")
        _utc(deadline, "order_expiry")
        if not as_of_utc < deadline:
            return False
    except (NativeTrxQuoteError, TypeError, ValueError):
        return False
    try:
        return _amount(record.get("usd_price"), "order_price") == _amount(amount_usd, "quote_price")
    except NativeTrxQuoteError:
        return False


def make_native_trx_quote(*, tenant, merchant_registry, order_id, sku,
                          usd_price, trx_usd_rate, observed_at_utc,
                          expires_at_utc, signing_key, now_utc,
                          trusted_order_registry):
    """Authenticated pricing, not an invoice. Called only after a durable order ID.

    A protected server clock MUST be passed at issuance. Rates older than
    five minutes or timestamped in the future cannot mint valid quotes.
    """
    key = _key(signing_key)
    if not isinstance(tenant, TenantDecision) or type(merchant_registry) is not dict:
        raise NativeTrxQuoteError("trusted_merchant_required")
    try:
        actual = registered_scope(
            host=tenant.host, brand=tenant.brand, registry=merchant_registry,
        )
    except (ValueError, TypeError, AttributeError):
        raise NativeTrxQuoteError("merchant_scope_invalid") from None
    if (actual != tenant or tenant.eligible_for_checkout_review is not True
            or tenant.payment_enabled is not False
            or tenant.invoice_created is not False):
        raise NativeTrxQuoteError("merchant_scope_not_approved")
    if (type(order_id) is not str or ORDER_RE.fullmatch(order_id) is None
            or type(sku) is not str or SKU_RE.fullmatch(sku) is None):
        raise NativeTrxQuoteError("order_or_sku_invalid")
    _utc(observed_at_utc, "rate_observation")
    _utc(expires_at_utc, "quote_expiry")
    _utc(now_utc, "server_issuance")
    if not (observed_at_utc <= now_utc < expires_at_utc
            and now_utc - observed_at_utc <= MAX_RATE_AGE
            and expires_at_utc - now_utc <= MAX_QUOTE_LIFETIME
            and timedelta(0) < expires_at_utc - observed_at_utc <= MAX_RATE_AGE):
        raise NativeTrxQuoteError("exchange_rate_expired")
    usd, rate = _amount(usd_price, "usd_price"), _amount(trx_usd_rate, "trx_rate")
    if not _order_is_authoritative(order_id, tenant.tenant_id, sku, usd,
                                    trusted_order_registry, now_utc):
        raise NativeTrxQuoteError("trusted_order_missing_or_mismatched")
    if rate < Decimal("0.000001") or rate > Decimal("10000"):
        raise NativeTrxQuoteError("exchange_rate_out_of_bounds")
    # Integral-SUN ceiling never quotes a transfer smaller than 1 SUN.
    sun = int((usd / rate * SUN).to_integral_value(rounding=ROUND_CEILING))
    if not 1 <= sun <= MAX_SUN:
        raise NativeTrxQuoteError("native_sun_amount_out_of_bounds")
    q = NativeTrxQuote(
        host=tenant.host, brand=tenant.brand, tenant_id=tenant.tenant_id,
        order_id=order_id, sku=sku, usd_price=format(usd, "f"),
        trx_usd_rate=format(rate, "f"), exact_amount_sun=sun,
        observed_at_utc=observed_at_utc.isoformat(),
        expires_at_utc=expires_at_utc.isoformat(), signature="",
    )
    mac = hmac.new(key, _message(q), sha256).hexdigest()
    return NativeTrxQuote(**{**q.__dict__, "signature": mac})


def verify_native_trx_quote(*, quote, merchant_registry, now_utc, signing_key,
                            trusted_order_registry):
    """Read-only verifier. An accurate order quote still cannot credit a payment."""
    if not isinstance(quote, NativeTrxQuote) or type(merchant_registry) is not dict:
        return False
    try:
        key = _key(signing_key)
        _utc(now_utc, "observation_time")
        start = datetime.fromisoformat(quote.observed_at_utc)
        end = datetime.fromisoformat(quote.expires_at_utc)
        _utc(start, "rate_observation")
        _utc(end, "quote_expiry")
        if (start > now_utc or now_utc >= end
                or not timedelta(0) < end - start <= MAX_RATE_AGE
                or type(quote.exact_amount_sun) is not int
                or not 1 <= quote.exact_amount_sun <= MAX_SUN
                or type(quote.signature) is not str
                or re.fullmatch(r"[0-9a-f]{64}", quote.signature) is None):
            return False
        actual = registered_scope(
            host=quote.host, brand=quote.brand, registry=merchant_registry,
        )
        if (not actual.eligible_for_checkout_review or
                actual.tenant_id != quote.tenant_id or
                actual.payment_enabled is not False or
                actual.invoice_created is not False):
            return False
        if (type(quote.order_id) is not str
                or ORDER_RE.fullmatch(quote.order_id) is None
                or type(quote.sku) is not str
                or SKU_RE.fullmatch(quote.sku) is None):
            return False
        usd = _amount(quote.usd_price, "usd_price")
        rate = _amount(quote.trx_usd_rate, "trx_rate")
        if not _order_is_authoritative(quote.order_id, quote.tenant_id, quote.sku,
                                       usd, trusted_order_registry, now_utc):
            return False
        if not Decimal("0.000001") <= rate <= Decimal("10000"):
            return False
        expected_sun = int((usd / rate * SUN).to_integral_value(rounding=ROUND_CEILING))
        if quote.exact_amount_sun != expected_sun:
            return False
        expected_mac = hmac.new(key, _message(quote), sha256).hexdigest()
        return hmac.compare_digest(expected_mac, quote.signature)
    except (NativeTrxQuoteError, ValueError, TypeError, AttributeError, ArithmeticError):
        return False
