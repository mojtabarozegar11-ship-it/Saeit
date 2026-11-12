"""Pure, side-effect-free reconciliation for verified service receipts.

Never treats a quote, order, blockchain broadcast or test payment as cash.
Caller must independently verify the settlement evidence with the provider.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable


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
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid monetary value") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("monetary value must be finite and nonnegative")
    return result


def reconcile(settlements: Iterable[Settlement], currency: str) -> dict:
    """Return confirmed gross, refunds and net; reject duplicate receipts.

    Unknown/unsupported records remain excluded, not counted as zero sales.
    Amounts are not converted across currencies.
    """
    if not currency or currency != currency.upper():
        raise ValueError("currency must be uppercase")
    seen = set()
    gross = Decimal("0")
    refunds = Decimal("0")
    accepted = 0
    excluded = 0
    for item in settlements:
        if item.currency != currency:
            excluded += 1
            continue
        if not item.receipt_id or not item.order_id:
            excluded += 1
            continue
        if item.receipt_id in seen:
            raise ValueError("duplicate settlement receipt")
        seen.add(item.receipt_id)
        amount = _money(item.amount)
        refund = _money(item.refunded_amount)
        if refund > amount:
            raise ValueError("refund exceeds settled amount")
        if (item.environment != "production" or not item.verified
                or item.status != "settled"):
            excluded += 1
            continue
        gross += amount
        refunds += refund
        accepted += 1
    return {"currency": currency, "confirmed_receipts": accepted,
            "excluded_records": excluded, "gross_settled": str(gross),
            "refunded": str(refunds), "net_received": str(gross - refunds)}
