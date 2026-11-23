"""Contract regression cases; no network, no payment, no DB mutation."""
from dataclasses import replace
import pytest

from prop_firm.invoice_price_snapshot_guard import (
    InvoicePriceSnapshot, InvoiceSnapshotRejected, require_supported_snapshot,
)
from prop_firm.versioned_invoice_pricing import PRICE_VERSION


@pytest.mark.parametrize("purchase_class,amount", [("first", 30_000_000), ("failed_retry", 18_000_000)])
def test_exact_persisted_snapshot(purchase_class, amount):
    snapshot = InvoicePriceSnapshot("mojprop-starter30", purchase_class, PRICE_VERSION, amount, "TRX", "tron-mainnet")
    assert require_supported_snapshot(snapshot) == amount


@pytest.mark.parametrize("change", [
    {"amount_sun": 18_000_000}, {"amount_sun": 30.0}, {"amount_sun": True},
    {"purchase_class": "failed_retry"}, {"purchase_class": "FIRST"},
    {"price_version": "legacy"}, {"currency": "USDT"},
    {"network": "tron-testnet"}, {"sku": "other"},
])
def test_reject_tampered_snapshot(change):
    original = InvoicePriceSnapshot("mojprop-starter30", "first", PRICE_VERSION, 30_000_000, "TRX", "tron-mainnet")
    with pytest.raises(InvoiceSnapshotRejected):
        require_supported_snapshot(replace(original, **change))


def test_reject_untyped_input():
    with pytest.raises(InvoiceSnapshotRejected):
        require_supported_snapshot({"amount_sun": 30_000_000})
