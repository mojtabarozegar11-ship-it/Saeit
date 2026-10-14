"""Fail-closed direct-wallet invoice builder for the approved MojPlayWin chess ebook.

Staging ONLY. This does not connect to a live Django checkout, collect payments
or prove control of the destination addresses. USD asset rates must originate
from a trusted provider fetched by server code, never from the buyer's browser.

An order-specific payment must be bound to a buyer-controlled sender through a
verified signed challenge and can settle only once after a chain proof passes.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import re
from typing import Callable

USD_AMOUNT = Decimal("7.50")
PRODUCT_ID = 72
MAX_QUOTE_SECONDS = 600
MAX_RATE_AGE_SECONDS = 90

NETWORKS = {
    "ETH": {
        "chain": "ethereum-mainnet",
        "units": 18,
        "recipient": "0x89149b01f59115B86553561F12438D2ADF517E75",
        "max_extra_units": 100000000,
    },
    "TRX": {
        "chain": "tron-mainnet",
        "units": 6,
        "recipient": "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
        "max_extra_units": 1000,
    },
}

# Backend allowlist, not client-provided API hostname or RPC URL.
TRUSTED_SPOT_PROVIDERS = frozenset({"coingecko", "coinbase"})


class InvoiceError(ValueError):
    pass


@dataclass(frozen=True)
class SpotRate:
    asset: str
    usd_per_asset: str
    provider: str
    observed_at_epoch: int


@dataclass(frozen=True)
class DirectInvoice:
    order_id: int
    product_id: int
    customer_id: int
    asset: str
    chain: str
    recipient: str
    expected_sender: str
    amount_smallest_units: int
    quote_price_usd: str
    quote_provider: str
    issued_at_epoch: int
    expires_at_epoch: int
    sender_proof_verified: bool


def build_direct_invoice(
    *, order_id: int, customer_id: int, asset: str, rate: SpotRate,
    expected_sender: str, sender_proof_verified: bool,
    now_epoch: int, invoice_dust: int,
    amount_is_unique: Callable[[str, str, int], bool],
) -> DirectInvoice:
    """Construct quote only after sender ownership proof and atomic uniqueness check.

    amount_is_unique MUST be backed by an order reservation under a database lock.
    A non-atomic callback is NOT suitable for production. The same quote must be
    persisted before any wallet payment instructions are displayed.
    """
    if type(order_id) is not int or order_id <= 0 or type(customer_id) is not int or customer_id <= 0:
        raise InvoiceError("Invalid order or customer")
    if asset not in NETWORKS or rate.asset != asset:
        raise InvoiceError("Unsupported asset or incorrect rate asset")
    if not sender_proof_verified or not expected_sender:
        raise InvoiceError("Verified buyer wallet signature is required")
    if not isinstance(expected_sender, str) or len(expected_sender) > 80:
        raise InvoiceError("Invalid buyer sender")
    # Format validation is not cryptographic ownership verification.
    if asset == "ETH" and not re.fullmatch(r"0x[0-9a-fA-F]{40}", expected_sender):
        raise InvoiceError("Invalid ETH sending address")
    if asset == "TRX":
        from mojplaywin_native_chain_verify import tron_address_to_hex
        tron_address_to_hex(expected_sender)

    cfg = NETWORKS[asset]
    if rate.provider not in TRUSTED_SPOT_PROVIDERS:
        raise InvoiceError("Untrusted USD pricing source")
    if type(now_epoch) is not int or type(rate.observed_at_epoch) is not int:
        raise InvoiceError("Invalid quote time")
    delta = now_epoch - rate.observed_at_epoch
    if delta < 0 or delta > MAX_RATE_AGE_SECONDS:
        raise InvoiceError("Rate is stale or in the future")

    try:
        price = Decimal(rate.usd_per_asset)
    except (InvalidOperation, TypeError, ValueError):
        raise InvoiceError("Invalid fiat exchange rate")
    if not price.is_finite() or price <= 0:
        raise InvoiceError("Invalid USD spot price")
    if type(invoice_dust) is not int or not (1 <= invoice_dust <= cfg["max_extra_units"]):
        raise InvoiceError("Unique invoice dust is out of range")
    scale = 10 ** cfg["units"]
    base_units = int((USD_AMOUNT / price * scale).to_integral_value(rounding=ROUND_CEILING))
    amount = base_units + invoice_dust
    if amount <= 0:
        raise InvoiceError("Invalid crypto amount")
    # No fallback to an unchecked invoice amount if the reservation fails.
    if not callable(amount_is_unique) or amount_is_unique(cfg["chain"], cfg["recipient"], amount) is not True:
        raise InvoiceError("Invoice amount could not be reserved uniquely")

    return DirectInvoice(
        order_id=order_id,
        customer_id=customer_id,
        product_id=PRODUCT_ID,
        asset=asset,
        chain=cfg["chain"],
        recipient=cfg["recipient"],
        expected_sender=expected_sender,
        amount_smallest_units=amount,
        quote_price_usd=str(USD_AMOUNT),
        quote_provider=rate.provider,
        issued_at_epoch=now_epoch,
        expires_at_epoch=now_epoch + MAX_QUOTE_SECONDS,
        sender_proof_verified=True,
    )


def can_submit_transaction(invoice: DirectInvoice, current_epoch: int) -> bool:
    # Expired invoices cannot accept newly submitted claims, but an on-chain
    # transaction broadcast during the quote window may be confirmed later.
    return (
        invoice.product_id == PRODUCT_ID
        and invoice.quote_price_usd == "7.50"
        and invoice.sender_proof_verified is True
        and type(current_epoch) is int
        and invoice.issued_at_epoch <= current_epoch <= invoice.expires_at_epoch
    )
