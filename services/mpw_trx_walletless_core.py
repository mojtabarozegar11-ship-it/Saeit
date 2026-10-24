"""Walletless TRX invoice safety kernel (isolated, not connected to public payments).

Purpose: allow a logged-in MojPlayWin buyer to receive a non-custodial TRX
payment invoice without signing an address-ownership challenge first.

This module does not make orders, receive payments, create ledger entries,
issue digital entitlements, or bypass the existing signature-based checkout.
The merchant service must provide and independently verify blockchain evidence
and install database uniqueness and row-locking before production integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, InvalidOperation
import re
from typing import Callable, Collection

SUN_PER_TRX = 1_000_000
MAX_QUOTE_AGE = timedelta(seconds=90)
INVOICE_TTL = timedelta(minutes=10)
MAX_MARKUP_USD = Decimal("0.005")
NETWORK = "tron-mainnet"
TX_ID = re.compile(r"^[0-9a-f]{64}$")
ADDRESS = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


class PaymentHold(Exception):
    """Fail closed: no ledger entry, receipt or product delivery permitted."""


@dataclass(frozen=True)
class InvoiceIntent:
    order_id: int
    customer_id: int
    network: str
    recipient: str
    amount_sun: int
    usd_total: Decimal
    issued_at: datetime
    expires_at: datetime
    quote_usd_per_trx: Decimal


@dataclass(frozen=True)
class SolidifiedTransfer:
    source_id: str
    tx_hash: str
    network: str
    recipient: str
    sender: str
    amount_sun: int
    block_time: datetime
    solidified: bool
    transfer_contract: bool
    execution_success: bool


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PaymentHold("Missing timezone-aware blockchain timestamp")
    return value.astimezone(timezone.utc)


def _money(value: Decimal, *, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise PaymentHold(f"Untrusted {label}")
    return value


def issue_intent(
    *,
    order_id: int,
    customer_id: int,
    recipient: str,
    usd_total: Decimal,
    usd_per_trx: Decimal,
    quote_observed_at: datetime,
    now: datetime,
    is_amount_reserved: Callable[[int], bool],
    random_below: Callable[[int], int],
) -> InvoiceIntent:
    """Compute one exact and permanently unique SUN amount.

    Called only inside a database atomic transaction with an allocation lock.
    The caller MUST persist the uniqueness key (network, recipient, amount_sun)
    forever, even after expiration. A collision is retried; never reuse amounts.
    No wallet address may be accepted from HTTP request data.
    """
    if type(order_id) is not int or order_id <= 0 or type(customer_id) is not int or customer_id <= 0:
        raise PaymentHold("A real authenticated order is required")
    if not isinstance(recipient, str) or not ADDRESS.fullmatch(recipient):
        raise PaymentHold("Invalid merchant TRON recipient")
    total = _money(usd_total, label="USD total")
    rate = _money(usd_per_trx, label="independently sourced TRX quote")
    current = _utc(now)
    observed = _utc(quote_observed_at)
    if not timedelta(0) <= current - observed <= MAX_QUOTE_AGE:
        raise PaymentHold("Quote has expired or has a future timestamp")
    if not callable(is_amount_reserved) or not callable(random_below):
        raise PaymentHold("Missing transactional uniqueness allocator")
    try:
        minimum = int((total / rate * SUN_PER_TRX).to_integral_value(rounding=ROUND_CEILING))
        max_extra = int((MAX_MARKUP_USD / rate * SUN_PER_TRX).to_integral_value(rounding=ROUND_FLOOR))
    except (OverflowError, InvalidOperation, ValueError) as exc:
        raise PaymentHold("Quote cannot be converted safely") from exc
    if minimum <= 0 or len(str(minimum)) > 18 or max_extra < 1:
        raise PaymentHold("Amount or uniqueness budget invalid")
    if max_extra > 500_000:
        max_extra = 500_000
    for _ in range(32):
        step = random_below(max_extra + 1)
        if type(step) is not int or not 0 <= step <= max_extra:
            raise PaymentHold("Untrusted amount entropy")
        amount = minimum + step
        if is_amount_reserved(amount):
            continue
        return InvoiceIntent(
            order_id=order_id, customer_id=customer_id,
            network=NETWORK, recipient=recipient, amount_sun=amount,
            usd_total=total, issued_at=current,
            expires_at=current + INVOICE_TTL,
            quote_usd_per_trx=rate,
        )
    raise PaymentHold("No unused amount; do not issue invoice")


def verify_two_source_transfer(
    invoice: InvoiceIntent,
    first: SolidifiedTransfer,
    second: SolidifiedTransfer,
    *,
    tx_previously_consumed: Callable[[str, str], bool],
) -> tuple[str, str]:
    """Return verified (tx_hash, sender) or fail CLOSED.

    first and second MUST come from two separately configured, independent
    server-side SolidityNode providers. Never construct either from browser
    JSON, a screenshot, a wallet callback or an unauthenticated webhook.
    The caller must re-check unique (network,tx_hash) inside the same SQL
    transaction that stores payment receipt + ledger + grant.
    """
    if not isinstance(invoice, InvoiceIntent):
        raise PaymentHold("Untrusted invoice")
    if invoice.network != NETWORK or not ADDRESS.fullmatch(invoice.recipient):
        raise PaymentHold("Wrong invoice network or destination")
    if not isinstance(invoice.amount_sun, int) or type(invoice.amount_sun) is not int or invoice.amount_sun <= 0:
        raise PaymentHold("Invalid invoice atomic amount")
    start = _utc(invoice.issued_at)
    end = _utc(invoice.expires_at)
    if not start < end <= start + INVOICE_TTL:
        raise PaymentHold("Invalid invoice lifetime")
    if not isinstance(first, SolidifiedTransfer) or not isinstance(second, SolidifiedTransfer):
        raise PaymentHold("Independent chain evidence is unavailable")
    if not first.source_id or not second.source_id or first.source_id == second.source_id:
        raise PaymentHold("Two different verification sources required")
    for record in (first, second):
        if (type(record.tx_hash) is not str or TX_ID.fullmatch(record.tx_hash) is None
                or record.network != NETWORK or record.recipient != invoice.recipient
                or type(record.amount_sun) is not int or record.amount_sun != invoice.amount_sun
                or record.solidified is not True or record.transfer_contract is not True
                or record.execution_success is not True
                or not isinstance(record.sender, str) or ADDRESS.fullmatch(record.sender) is None):
            raise PaymentHold("Mainnet transfer evidence did not match")
        stamp = _utc(record.block_time)
        if not start <= stamp <= end:
            raise PaymentHold("Payment outside issued invoice window")
    if (first.tx_hash != second.tx_hash
            or first.sender != second.sender
            or _utc(first.block_time) != _utc(second.block_time)):
        raise PaymentHold("Independent chain observations disagree")
    if not callable(tx_previously_consumed):
        raise PaymentHold("Duplicate-payment registry unavailable")
    if tx_previously_consumed(NETWORK, first.tx_hash):
        raise PaymentHold("Transaction already used")
    return first.tx_hash, first.sender
