"""Pure, side-effect-free reconciliation for verified service receipts.

Never treats a quote, order, blockchain broadcast or test payment as cash.
Caller must independently verify the settlement evidence with the provider.
The verified boolean is a caller assertion, never standalone proof of cash.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import re
from typing import Iterable

_CURRENCY = re.compile(r"[A-Z][A-Z0-9_-]{1,15}\Z", re.ASCII)
_MONEY = re.compile(r"(?:0|[1-9][0-9]{0,29})(?:\.[0-9]{1,18})?\Z", re.ASCII)
_MAX_RECEIPTS = 100_000
_MAX_IDENTIFIER_LENGTH = 256


@dataclass(frozen=True)
class Settlement:
    order_id: str
    currency: str
    amount: str
    receipt_id: str
    status: str
    verified: bool
    refunded_amount: str = "0"
    environment: str = "production"


def _money(value: str) -> Decimal:
    """Parse only finite, nonnegative, bounded, exact decimal strings.

    Reject implicit float/int/string coercion, exponent notation and huge
    coefficient or fractional precision. No rounding or conversion is done.
    """
    if not isinstance(value, str) or not _MONEY.fullmatch(value):
        raise ValueError("monetary value must be a bounded exact decimal string")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid monetary value") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("monetary value must be finite and nonnegative")
    return result


def _identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAX_IDENTIFIER_LENGTH
        and value == value.strip()
        and value.isprintable()
        and not any(ch.isspace() for ch in value)
    )


def reconcile(settlements: Iterable[Settlement], currency: str) -> dict:
    """Return confirmed gross, refunds and net; reject duplicate receipts.

    Unknown/unsupported records remain excluded, not counted as zero sales.
    Amounts are not converted across currencies.
    """
    if not isinstance(currency, str) or not _CURRENCY.fullmatch(currency):
        raise ValueError("currency must be a bounded uppercase currency code")
    seen = set()
    gross = Decimal("0")
    refunds = Decimal("0")
    accepted = 0
    excluded = 0
    inspected = 0
    try:
        iterator = iter(settlements)
    except TypeError as exc:
        raise ValueError("settlements must be iterable") from exc
    for item in iterator:
        inspected += 1
        if inspected > _MAX_RECEIPTS:
            raise ValueError("receipt batch too large")
        if not isinstance(item, Settlement):
            raise ValueError("record must be a Settlement")
        if item.currency != currency:
            excluded += 1
            continue
        if not _identifier(item.receipt_id) or not _identifier(item.order_id):
            excluded += 1
            continue
        if item.receipt_id in seen:
            raise ValueError("duplicate settlement receipt")
        seen.add(item.receipt_id)
        amount = _money(item.amount)
        refund = _money(item.refunded_amount)
        if refund > amount:
            raise ValueError("refund exceeds settled amount")
        if (item.environment != "production" or item.verified is not True
                or item.status != "settled"):
            excluded += 1
            continue
        # Ensure exact summation under the 100,000-record, 30+18-digit cap.
        with localcontext() as exact:
            exact.prec = 64
            gross += amount
            refunds += refund
        accepted += 1
    with localcontext() as exact:
        exact.prec = 64
        net = gross - refunds
    return {"currency": currency, "confirmed_receipts": accepted,
            "excluded_records": excluded, "gross_settled": str(gross),
            "refunded": str(refunds), "net_received": str(net)}
