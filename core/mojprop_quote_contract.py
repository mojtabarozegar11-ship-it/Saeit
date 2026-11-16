"""Pure, buyer-safe Moj Prop quote contract.

This module turns an already reviewed/issued Django offer into a stable
commercial snapshot. It never charges, sends, delivers, or marks revenue.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import re
import unicodedata

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
    # Customer-facing price/scope/exclusion fields must not permit invisible
    # Unicode formatting or bidirectional overrides that spoof contract terms.
    for index, ch in enumerate(value):
        if ch == "\u200c" and 0 < index < len(value) - 1:
            # Persian/Arabic uses ZWNJ as orthographic half-space, e.g.
            # "می‌شود". Allow it ONLY between two Arabic-script letters.
            # Keep all direction overrides, non-word ZWNJ and other Cf denied.
            left = unicodedata.name(value[index - 1], "")
            right = unicodedata.name(value[index + 1], "")
            if left.startswith("ARABIC LETTER ") and right.startswith("ARABIC LETTER "):
                continue
        if (unicodedata.category(ch) in ("Cf", "Zl", "Zp", "Cs")
                or ord(ch) in range(0x202A, 0x202F)
                or ord(ch) in range(0x2066, 0x206A)):
            raise QuoteContractError("unsafe invisible quote formatting in " + name)
    if name == "title" and any(ch in value for ch in ("\n", "\t", "\u0085", "\u2028", "\u2029")):
        raise QuoteContractError("title must not inject a second proposal line")
    return value.strip()

def validate_acceptance_reference(value):
    """Return normalized buyer acceptance evidence or fail closed."""
    reference = _text(value, "acceptance reference", 6, 180)
    # Audit evidence must not contain hidden direction overrides or terminal
    # controls that can alter the apparent buyer approval in logs and reports.
    forbidden_bidi = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
    if any(ord(ch) < 32 or 0x7F <= ord(ch) <= 0x9F
           or ord(ch) in forbidden_bidi
           or unicodedata.category(ch) in ("Cf", "Zl", "Zp", "Cc", "Cs")
           for ch in reference):
        raise QuoteContractError("invalid acceptance reference")
    return reference


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
    if type(amount) is not Decimal or not amount.is_finite() or amount <= 0:
        raise QuoteContractError("finite positive decimal amount required")
    try:
        # Match the Django DecimalField(max_digits=12, decimal_places=2).
        # An extreme finite Decimal must be a domain rejection, never a 500.
        if (amount > Decimal("9999999999.99")
                or amount != amount.quantize(Decimal("0.01"))):
            raise QuoteContractError("bounded two-decimal amount required")
    except InvalidOperation as exc:
        raise QuoteContractError("invalid decimal quote amount") from exc
    currency = getattr(offer, "currency", None)
    if type(currency) is not str or currency not in _CURRENCIES:
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
        if accepted_at < issued_at or accepted_at > moment or accepted_at >= expires_at:
            raise QuoteContractError("acceptance is outside the quote window")
        validate_acceptance_reference(
            getattr(offer, "acceptance_reference", None)
        )
    elif (accepted_at is not None
          or bool(getattr(offer, "acceptance_reference", None))):
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


def render_public_quote(
    snapshot: dict, *, service_route: str, product_id: int | None,
) -> str:
    """Display a checked, unpaid quote without spoofable top-level headings.

    No financial operation occurs. The caller must independently validate
    the current issued offer by calling make_quote_snapshot first.
    """
    required = {
        "schema", "reference", "version", "title", "scope", "exclusions",
        "amount", "currency", "delivery_days", "status", "reviewed_at",
        "issued_at", "expires_at", "payment_status", "delivery_status",
        "revenue_status", "payable",
    }
    if type(snapshot) is not dict or set(snapshot) != required:
        raise QuoteContractError("invalid public quote snapshot shape")
    if (snapshot["schema"] != "mojprop.quote.v1"
            or snapshot["status"] not in ("issued", "accepted")
            or snapshot["payment_status"] != "not_collected"
            or snapshot["delivery_status"] != "not_delivered"
            or snapshot["revenue_status"] != "not_received"
            or snapshot["payable"] is not False):
        raise QuoteContractError("public quote cannot attest payment or fulfillment")
    if (type(service_route) is not str or service_route not in
            ("blueprint", "signals", "brief", "audit", "digital")):
        raise QuoteContractError("unrecognized customer service route")
    if (product_id is not None and
            (type(product_id) is not int or product_id <= 0)):
        raise QuoteContractError("invalid catalog product identity")
    if service_route == "digital" and product_id is None:
        raise QuoteContractError("digital product quote requires a catalog product id")
    reference = snapshot["reference"]
    if type(reference) is not str or _REFERENCE.fullmatch(reference) is None:
        raise QuoteContractError("invalid buyer request reference")
    version = snapshot["version"]
    days = snapshot["delivery_days"]
    if (type(version) is not int or not 1 <= version <= 999
            or type(days) is not int or not 1 <= days <= 90):
        raise QuoteContractError("invalid public quote version or delivery")
    title = _text(snapshot["title"], "title", 3, 180)
    scope = _text(snapshot["scope"], "scope", 50, 10000)
    exclusions = _text(snapshot["exclusions"], "exclusions", 10, 5000)
    amount = snapshot["amount"]
    currency = snapshot["currency"]
    if (type(amount) is not str
            or re.fullmatch(r"(?:0|[1-9][0-9]{0,9})\.[0-9]{2}", amount) is None
            or Decimal(amount) <= 0
            or type(currency) is not str or currency not in _CURRENCIES):
        raise QuoteContractError("invalid public quote price")
    for name in ("reviewed_at", "issued_at", "expires_at"):
        value = snapshot[name]
        if type(value) is not str or len(value) > 40 or "\n" in value:
            raise QuoteContractError("invalid public quote timestamp")

    def quote_lines(value: str) -> list[str]:
        # A newline (including Unicode U+0085) in scope must never create
        # a forged 'Quoted amount:' or 'Payment received:' top-level header.
        return ["  | " + line.replace("\t", "    ") for line in value.splitlines()]

    lines = [
        "MOJ PROP / mojtaba.bot.ai - MANUAL PROPOSAL (NOT A PAYMENT INVOICE)",
        f"Reference: {reference} / version {version}",
        f"Service route: {service_route}",
        f"Catalog product ID: {product_id if product_id is not None else 'n/a'}",
        f"Deliverable: {title}",
        "Scope (quoted customer terms):",
        *quote_lines(scope),
        "Exclusions (quoted customer terms):",
        *quote_lines(exclusions),
        f"Quoted amount: {amount} {currency}",
        f"Target delivery: {days} day(s) after a separate agreement.",
        f"Proposal status: {snapshot['status']}; expires: {snapshot['expires_at']}",
        "No payment has been collected; a lawful payment route and written agreement are required.",
        "No service has been delivered; this quote is not proof of a paid order.",
    ]
    return "\n".join(lines) + "\n"
