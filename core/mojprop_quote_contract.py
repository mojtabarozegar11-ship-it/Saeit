"""Pure, buyer-safe Moj Prop quote contract.

This module turns an already reviewed/issued Django offer into a stable
commercial snapshot. It never charges, sends, delivers, or marks revenue.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import re

class QuoteContractError(ValueError):
    pass

_CURRENCIES = frozenset(("USD", "IRR"))
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,79}$")

def _aware(value, name):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise QuoteContractError(name + " must be timezone-aware")
    return value.astimezone(timezone.utc)

def _text(value, name, minimum, maximum):
    if (type(value) is not str or not minimum <= len(value.strip()) <= maximum
            or any((ord(ch) < 32 and ch not in "\n\t")
                   or 0xD800 <= ord(ch) <= 0xDFFF for ch in value)):
        raise QuoteContractError("invalid " + name)
    return value.strip()

def make_quote_snapshot(offer, *, now=None):
    """Return a deterministic quote snapshot; payment remains explicitly absent."""
    if offer is None:
        raise QuoteContractError("offer is required")
    status = getattr(offer, "status", None)
    if status not in ("issued", "accepted"):
        raise QuoteContractError("only issued or accepted offers are quotable")
    lead = getattr(offer, "lead", None)
    reference = getattr(lead, "request_id", None)
    if type(reference) is not str or _REFERENCE.fullmatch(reference) is None:
        raise QuoteContractError("stable buyer request reference required")
    title = _text(getattr(offer, "title", None), "title", 3, 180)
    scope = _text(getattr(offer, "scope", None), "scope", 50, 10000)
    exclusions = _text(
        getattr(offer, "exclusions", None),
        "exclusions",
        10,
        5000,
    )
    amount = getattr(offer, "amount", None)
    if (type(amount) is not Decimal or not amount.is_finite()
            or amount <= 0 or amount != amount.quantize(Decimal("0.01"))):
        raise QuoteContractError("finite positive decimal amount required")
    currency = getattr(offer, "currency", None)
    if currency not in _CURRENCIES:
        raise QuoteContractError("unsupported quote currency")
    delivery_days = getattr(offer, "delivery_days", None)
    if type(delivery_days) is not int or not 1 <= delivery_days <= 90:
        raise QuoteContractError("invalid delivery days")
    version = getattr(offer, "version", None)
    if type(version) is not int or not 1 <= version <= 999:
        raise QuoteContractError("invalid immutable quote version")
    moment = _aware(now if now is not None else datetime.now(timezone.utc), "now")
    issued_at = _aware(getattr(offer, "issued_at", None), "issued_at")
    expires_at = _aware(getattr(offer, "expires_at", None), "expires_at")
    if not issued_at <= moment < expires_at:
        raise QuoteContractError("quote is not currently active")
    if expires_at - issued_at > timedelta(days=90):
        raise QuoteContractError("quote validity window is too long")
    reviewed_at = _aware(getattr(offer, "reviewed_at", None), "reviewed_at")
    if issued_at < reviewed_at:
        raise QuoteContractError("issuance precedes review")
    accepted_at = getattr(offer, "accepted_at", None)
    if status == "accepted":
        accepted_at = _aware(accepted_at, "accepted_at")
        if accepted_at < issued_at or accepted_at >= expires_at:
            raise QuoteContractError("acceptance is outside the quote window")
        _text(
            getattr(offer, "acceptance_reference", None),
            "acceptance reference",
            6,
            180,
        )
    elif accepted_at is not None:
        raise QuoteContractError("issued quote cannot carry acceptance evidence")
    return {
        "schema": "mojprop.quote.v1",
        "reference": reference,
        "version": version,
        "title": title,
        "scope": scope,
        "exclusions": exclusions,
        "amount": format(amount, "f"),
        "currency": currency,
        "delivery_days": delivery_days,
        "status": status,
        "reviewed_at": reviewed_at.isoformat(),
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "payment_status": "not_collected",
        "delivery_status": "not_delivered",
        "revenue_status": "not_received",
        "payable": False,
    }
