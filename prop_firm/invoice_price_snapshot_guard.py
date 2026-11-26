"""Fail-closed invoice snapshot validation for the MOJ PROP price branch.

NOT connected to checkout or settlement. This validates only persisted pricing
metadata, not blockchain finality, payment ownership, redemption or delivery.
The caller must read immutable database fields, not request parameters.
"""
from dataclasses import dataclass

from .versioned_invoice_pricing import (
    FIRST_FEE_SUN, FAILED_RETRY_FEE_SUN, PRICE_VERSION, PurchaseClass,
)


class InvoiceSnapshotRejected(ValueError):
    pass


@dataclass(frozen=True)
class InvoicePriceSnapshot:
    sku: str
    purchase_class: str
    price_version: str
    amount_sun: int
    currency: str
    network: str


def require_supported_snapshot(snapshot: InvoicePriceSnapshot) -> int:
    """Return expected SUN only for an exact, known persisted invoice contract.

    No default, coercion, float, fallback to 30 TRX, or acceptance of an
    unknown historical price version. Historical invoices require their own
    explicit versioned validator and must not be silently repriced.
    """
    if type(snapshot) is not InvoicePriceSnapshot:
        raise InvoiceSnapshotRejected("persisted invoice snapshot required")
    if snapshot.sku != "mojprop-starter30":
        raise InvoiceSnapshotRejected("unknown SKU")
    if snapshot.price_version != PRICE_VERSION:
        raise InvoiceSnapshotRejected("unknown price version")
    if snapshot.currency != "TRX" or snapshot.network != "tron-mainnet":
        raise InvoiceSnapshotRejected("unsupported currency or network")
    if type(snapshot.amount_sun) is not int:
        raise InvoiceSnapshotRejected("integer SUN required")
    amounts = {
        PurchaseClass.FIRST.value: FIRST_FEE_SUN,
        PurchaseClass.FAILED_RETRY.value: FAILED_RETRY_FEE_SUN,
    }
    if type(snapshot.purchase_class) is not str or snapshot.purchase_class not in amounts:
        raise InvoiceSnapshotRejected("unknown purchase class")
    expected = amounts[snapshot.purchase_class]
    if snapshot.amount_sun != expected:
        raise InvoiceSnapshotRejected("invoice amount and purchase class disagree")
    return expected
