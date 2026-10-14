"""Read-only, fail-closed entitlement checks for MojPlayWin's ETH/TRX ebook.

Not wired into live URLs. No payment state is changed by these functions.
Actual blockchain validation and atomic transaction reservation belong to
the settlement service, not to the customer-facing download view.
"""
from decimal import Decimal
import re

from core.models import Order, LedgerEntry
from .models import NativeInvoice, NativeChainTransfer

PRODUCT_ID = 72
BOOK_ID = "mojplaywin-chess-improvement-2026"
PRICE_USD = Decimal("7.50")
NETWORK_BY_ASSET = {"ETH": "ethereum-mainnet", "TRX": "tron-mainnet"}


def qualified_order(order_id, customer_id):
    """True only for a single authorized active-book order awaiting payment."""
    if not isinstance(order_id, int) or not isinstance(customer_id, int):
        return False
    order=Order.objects.filter(pk=order_id,customer_id=customer_id).first()
    if order is None or order.status != "pending":
        return False
    if order.currency != "USD" or order.total != PRICE_USD:
        return False
    items=list(order.items.select_related("product").all())
    if len(items)!=1 or items[0].quantity != 1:
        return False
    item=items[0]
    product=item.product
    if product.pk != PRODUCT_ID or item.unit_price!=PRICE_USD or item.currency!="USD":
        return False
    if product.active is not True or product.currency!="USD" or product.price!=PRICE_USD:
        return False
    info=product.metadata if isinstance(product.metadata,dict) else {}
    return (
        info.get("product_id")==BOOK_ID and
        info.get("asset_verified") is True and
        info.get("payment_live") is True
    )


def can_download_paid_native_order(order_id, customer_id):
    """Require the paid Django order AND durable verified one-to-one chain proof."""
    if not isinstance(order_id,int) or not isinstance(customer_id,int):
        return False
    order=Order.objects.filter(pk=order_id,customer_id=customer_id,status="paid").first()
    if order is None or order.total!=PRICE_USD or order.currency!="USD":
        return False
    items=list(order.items.select_related("product").all())
    if len(items)!=1 or items[0].quantity!=1 or items[0].product_id!=PRODUCT_ID:
        return False
    product=items[0].product
    if not product.active or product.price!=PRICE_USD or product.currency!="USD":
        return False
    info=product.metadata if isinstance(product.metadata,dict) else {}
    if (info.get("product_id")!=BOOK_ID or info.get("asset_verified") is not True
            or info.get("payment_live") is not True):
        return False
    invoice=NativeInvoice.objects.filter(
        order=order,customer_id=customer_id,product=product,
        status=NativeInvoice.Status.PAID,usd_amount=PRICE_USD,
    ).first()
    if invoice is None or not invoice.wallet_challenge_id:
        return False
    if invoice.sender_signature_verified_at is None:
        return False
    if NETWORK_BY_ASSET.get(invoice.asset)!=invoice.network:
        return False
    try:
        transfer=invoice.chain_transfer
    except NativeChainTransfer.DoesNotExist:
        return False
    expected_backend = (
        "ethereum-mainnet-verified" if invoice.network == "ethereum-mainnet"
        else "tron-solidity-verified"
    )
    expected_hash = (
        r"0x[0-9a-f]{64}" if invoice.asset == "ETH"
        else r"[0-9a-f]{64}"
    )
    valid_proof = (
        transfer.network == invoice.network
        and transfer.recipient_address.lower() == invoice.merchant_address.lower()
        and transfer.sender_address.lower() == invoice.verified_sender_address.lower()
        and transfer.amount_atomic == invoice.amount_atomic
        and re.fullmatch(r"[0-9a-f]{64}", transfer.evidence_digest or "") is not None
        and re.fullmatch(expected_hash, transfer.tx_hash or "") is not None
        and transfer.verification_backend == expected_backend
    )
    if not valid_proof:
        return False
    ledger_ref = "native-crypto:" + invoice.network + ":" + transfer.tx_hash
    return LedgerEntry.objects.filter(
        order=order,
        payment_intent__isnull=True,
        entry_type="payment",
        currency="USD",
        amount=PRICE_USD,
        reference=ledger_ref,
        metadata__native_invoice_id=invoice.pk,
        metadata__network=invoice.network,
        metadata__tx_hash=transfer.tx_hash,
        metadata__evidence_digest=transfer.evidence_digest,
    ).exists()
