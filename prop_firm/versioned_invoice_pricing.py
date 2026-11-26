"""Immutable server-side MOJ PROP price decisions; no payment side effects.

This module is deliberately NOT wired to live invoice issuance. Integration
requires eligibility locking, unique redemption, database migrations and E
release authorization. Never accept a client-supplied amount or price class.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

SUN_PER_TRX = 1_000_000
FIRST_FEE_SUN = 30 * SUN_PER_TRX
FAILED_RETRY_FEE_SUN = 18 * SUN_PER_TRX
PRICE_VERSION = "2026-11-23/first30-failed-retry18"


class PurchaseClass(str, Enum):
    FIRST = "first"
    FAILED_RETRY = "failed_retry"


class PriceDecisionRejected(ValueError):
    """A price cannot be issued from unverified server-side evidence."""


@dataclass(frozen=True)
class ImmutablePriceDecision:
    sku: str
    purchase_class: PurchaseClass
    price_version: str
    amount_sun: int
    currency: str = "TRX"
    network: str = "tron-mainnet"


def decide_price(*, sku: str, purchase_class: PurchaseClass,
                 eligible_failed_retry: bool = False) -> ImmutablePriceDecision:
    """Return an exact price only after the caller has verified eligibility.

    eligible_failed_retry must come from a locked, server-verified failed
    challenge and an unused redemption, not from HTTP form fields. The caller
    must persist this decision and consume redemption atomically.
    """
    if sku != "mojprop-starter30":
        raise PriceDecisionRejected("unsupported SKU")
    if type(purchase_class) is not PurchaseClass:
        raise PriceDecisionRejected("purchase class must be server-selected")
    if type(eligible_failed_retry) is not bool:
        raise PriceDecisionRejected("eligibility must be a verified boolean")
    if purchase_class is PurchaseClass.FIRST:
        if eligible_failed_retry:
            raise PriceDecisionRejected("retry evidence cannot price first purchase")
        amount = FIRST_FEE_SUN
    elif purchase_class is PurchaseClass.FAILED_RETRY:
        if not eligible_failed_retry:
            raise PriceDecisionRejected("verified unused failed-retry entitlement required")
        amount = FAILED_RETRY_FEE_SUN
    else:
        raise PriceDecisionRejected("unsupported purchase class")
    return ImmutablePriceDecision(sku, purchase_class, PRICE_VERSION, amount)


def exact_settlement_amount(*, invoice_amount_sun: int,
                            transfer_amount_sun: int) -> bool:
    """Check exact immutable invoice amount; never use a global 30 TRX check.

    This is arithmetic only; it does NOT prove transaction finality, sender,
    sole recipient, network, provider independence, uniqueness or expiry.
    """
    if type(invoice_amount_sun) is not int or type(transfer_amount_sun) is not int:
        return False
    if invoice_amount_sun not in (FIRST_FEE_SUN, FAILED_RETRY_FEE_SUN):
        return False
    return transfer_amount_sun == invoice_amount_sun
