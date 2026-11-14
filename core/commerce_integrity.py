"""Fail-closed order/payment evidence shape contracts.

Pure helpers only: no provider API, database changes, customer messages,
invoice execution, delivery, money movement or background workers.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import re

IDENTIFIER = re.compile(r"[1-9][0-9]{0,9}\Z")
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{7,127}\Z")
CURRENCY = re.compile(r"[A-Z]{3,10}\Z")
PROVIDER = re.compile(r"[a-z][a-z0-9_-]{1,49}\Z")
EVENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}\Z")
PROVIDER_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")
AMOUNT = re.compile(r"(0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?\Z")
BAD_PROVIDERS = frozenset(("demo", "test", "sandbox", "not_configured"))
MAX_QUANTITY = 100
MAX_MONEY = Decimal("999999999999.99")


def strict_id(raw):
    if type(raw) is int:
        candidate = raw
    elif type(raw) is str and IDENTIFIER.fullmatch(raw):
        candidate = int(raw)
    else:
        raise ValueError("IDENTIFIER_INVALID")
    if not 1 <= candidate <= 2147483647:
        raise ValueError("IDENTIFIER_INVALID")
    return candidate


def strict_quantity(raw):
    # Exclude booleans, floats, exponents, whitespace and arbitrary objects.
    quantity = strict_id(raw)
    if quantity > MAX_QUANTITY:
        raise ValueError("QUANTITY_LIMIT_EXCEEDED")
    return quantity


def strict_key(raw):
    if type(raw) is not str or KEY.fullmatch(raw) is None:
        raise ValueError("IDEMPOTENCY_KEY_INVALID")
    return raw


def valid_currency(raw):
    return type(raw) is str and CURRENCY.fullmatch(raw) is not None


def valid_provider(raw):
    return (type(raw) is str and PROVIDER.fullmatch(raw) is not None
            and raw not in BAD_PROVIDERS)


def valid_event_id(raw):
    return type(raw) is str and EVENT.fullmatch(raw) is not None


def valid_provider_ref(raw):
    return type(raw) is str and PROVIDER_REF.fullmatch(raw) is not None


def exact_money(raw):
    """Return positive, finite, two-decimal-or-less exact money, else reject."""
    if type(raw) is not Decimal:
        raise ValueError("MONEY_INVALID")
    if not raw.is_finite() or raw <= 0 or raw > MAX_MONEY:
        raise ValueError("MONEY_INVALID")
    if raw.as_tuple().exponent < -2:
        # 1.000 is not an extra cent but cannot safely fit the defined
        # decimal scale in a source contract without explicit normalization.
        raise ValueError("MONEY_SCALE_INVALID")
    return raw


def exact_total(price, quantity):
    exact_money(price)
    if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError("QUANTITY_INVALID")
    with localcontext() as context:
        context.prec = 40
        total = price * quantity
    exact_money(total)
    return total


def provider_amount(raw):
    # Signed JSON must transmit money as an exact decimal string, not floats.
    if type(raw) is not str or AMOUNT.fullmatch(raw) is None:
        raise ValueError("WEBHOOK_AMOUNT_INVALID")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise ValueError("WEBHOOK_AMOUNT_INVALID") from None
    return exact_money(amount)



def parse_strict_webhook_json(raw):
    """No duplicate or nonfinite fields; JSON object only, never form/array."""
    import json

    def _pairs_unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("WEBHOOK_DUPLICATE_FIELD")
            obj[key] = value
        return obj

    def _no_nonfinite(_value):
        raise ValueError("WEBHOOK_NONFINITE_JSON")

    if type(raw) is not bytes or not 1 <= len(raw) <= 16384:
        raise ValueError("WEBHOOK_BODY_SIZE_INVALID")
    try:
        result = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_pairs_unique, parse_constant=_no_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("WEBHOOK_INVALID_JSON") from None
    if type(result) is not dict:
        raise ValueError("WEBHOOK_OBJECT_REQUIRED")
    if set(result).difference({
        "event_type", "payment_intent_id", "amount",
        "currency", "provider_reference", "event_id",
    }):
        raise ValueError("WEBHOOK_UNEXPECTED_FIELDS")
    return result


def ledger_reference(provider, event_id):
    """Stable, unambiguous fixed-width ledger ref shared by revenue auditor."""
    if not valid_provider(provider) or not valid_event_id(event_id):
        raise ValueError("WEBHOOK_EVENT_IDENTIFIER_INVALID")
    key = (provider + "\x00" + event_id).encode("ascii")
    return "payment:" + hashlib.sha256(key).hexdigest()


def valid_provider_allowlist(value, provider):
    """Explicit configured provider. Never use an implicit demo fallback."""
    if type(value) not in (tuple, list, frozenset):
        return False
    if not value or len(value) > 20:
        return False
    if any(not valid_provider(v) for v in value):
        return False
    return valid_provider(provider) and provider in value
