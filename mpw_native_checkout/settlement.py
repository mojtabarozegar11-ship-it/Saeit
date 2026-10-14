"""Automatic verified native ETH/TRX settlement, STAGING ONLY.

Never import into public URLconf or schedule against live payments before
receiver-wallet ownership, RPC trust, buyer proof, rate and refund policies are
validated. Backend code, not a browser form, supplies trusted RPC callbacks.
"""
import hashlib
import json
import re
from decimal import Decimal
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import LedgerEntry, OrderItem
from .entitlements import BOOK_ID, PRICE_USD, PRODUCT_ID, NETWORK_BY_ASSET
from .models import NativeInvoice, NativeChainTransfer
from scripts.mojplaywin_native_chain_verify import (
    LockedQuote, VerificationError, verify_eth_transfer, verify_trx_transfer,
)

RECEIVERS = {
    "ETH": "0x89149b01f59115B86553561F12438D2ADF517E75",
    "TRX": "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
}


class SettlementRejected(ValueError):
    pass


def _validate(invoice):
    order = invoice.order
    p = invoice.product
    metadata = p.metadata if isinstance(p.metadata, dict) else {}
    if p.pk != PRODUCT_ID or not p.active or p.currency != "USD" or p.price != PRICE_USD:
        raise SettlementRejected("Book is not authorized for live settlement")
    if metadata.get("product_id") != BOOK_ID or metadata.get("asset_verified") is not True:
        raise SettlementRejected("Book asset is not verified")
    if metadata.get("payment_live") is not True:
        raise SettlementRejected("Live payment approval has not been granted")
    if order.status != "pending" or order.currency != "USD" or order.total != PRICE_USD:
        raise SettlementRejected("Order not eligible")
    if order.customer_id != invoice.customer_id or invoice.usd_amount != PRICE_USD:
        raise SettlementRejected("Invoice customer/price mismatch")
    if NETWORK_BY_ASSET.get(invoice.asset) != invoice.network:
        raise SettlementRejected("Coin-network mismatch")
    if invoice.merchant_address.lower() != RECEIVERS[invoice.asset].lower():
        raise SettlementRejected("Wrong receiving wallet")
    if invoice.merchant_ownership_verified_at is None or invoice.sender_signature_verified_at is None:
        raise SettlementRejected("Wallet signatures have not been independently proven")
    if not invoice.wallet_challenge_id or not invoice.verified_sender_address:
        raise SettlementRejected("Buyer proof missing")
    if not (invoice.issued_at < invoice.expires_at <= invoice.issued_at + timedelta(minutes=10)):
        raise SettlementRejected("Quote time window invalid")
    if not invoice.price_observed_at <= invoice.issued_at <= invoice.price_observed_at + timedelta(seconds=90):
        raise SettlementRejected("Fiat quote freshness unknown")
    if invoice.price_source not in {"coingecko", "coinbase"} or invoice.usd_per_asset <= 0:
        raise SettlementRejected("Fiat quote not trusted")
    if not invoice.amount_atomic.isascii() or not invoice.amount_atomic.isdecimal():
        raise SettlementRejected("Invalid atomic unit text")
    if str(int(invoice.amount_atomic)) != invoice.amount_atomic or int(invoice.amount_atomic) <= 0:
        raise SettlementRejected("Atomic unit format noncanonical")
    lines = list(OrderItem.objects.filter(order=order).select_related("product"))
    if len(lines) != 1 or lines[0].product_id != p.pk:
        raise SettlementRejected("Order items do not match chess book")
    if lines[0].quantity != 1 or lines[0].unit_price != PRICE_USD or lines[0].currency != "USD":
        raise SettlementRejected("Order amount/item mismatch")


def settle_native_invoice(invoice_id, tx_hash, *, ethereum_rpc=None, tron_solidity_rpc=None):
    """Automatically confirm one order only after independent mainnet proof.

    Returns one of paid / already_paid. Exceptions must be handled by a
    bounded background job that retries transient RPC errors but NEVER
    auto-approves unverified payments or publishes the ebook.
    """
    invoice = NativeInvoice.objects.select_related("order", "product").filter(pk=invoice_id).first()
    if invoice is None:
        raise SettlementRejected("Invoice not found")
    normalized_hash = str(tx_hash).lower()
    valid_hash = (
        re.fullmatch(r"0x[0-9a-f]{64}", normalized_hash)
        if invoice.network == "ethereum-mainnet"
        else re.fullmatch(r"[0-9a-f]{64}", normalized_hash)
        if invoice.network == "tron-mainnet"
        else None
    )
    if valid_hash is None:
        raise SettlementRejected("Invalid chain transaction ID")
    if invoice.status == NativeInvoice.Status.PAID:
        if NativeChainTransfer.objects.filter(
            invoice=invoice, network=invoice.network, tx_hash=normalized_hash,
        ).exists():
            return "already_paid"
        raise SettlementRejected("Invoice already paid with a different transaction")
    if invoice.status != NativeInvoice.Status.AWAITING:
        raise SettlementRejected("Invoice is not awaiting payment")
    _validate(invoice)

    quote = LockedQuote(
        order_id=invoice.order_id,
        network=invoice.network,
        smallest_units=int(invoice.amount_atomic),
        expected_sender=invoice.verified_sender_address,
        created_at_ms=int(invoice.issued_at.timestamp()) * 1000,
        expires_at_ms=int(invoice.expires_at.timestamp()) * 1000,
        quote_currency="USD", quote_amount="7.50",
    )
    if invoice.asset == "ETH":
        if ethereum_rpc is None:
            raise SettlementRejected("Trusted Ethereum RPC is missing")
        proof = verify_eth_transfer(tx_hash, quote, ethereum_rpc)
        backend = "ethereum-mainnet-verified"
    elif invoice.asset == "TRX":
        if tron_solidity_rpc is None:
            raise SettlementRejected("Trusted TRON solidity API is missing")
        proof = verify_trx_transfer(tx_hash, quote, tron_solidity_rpc)
        backend = "tron-solidity-verified"
    else:
        raise SettlementRejected("Unrecognized chain")

    # Receipt verification happens outside the transaction. Revalidate every
    # relevant field under DB row locks before writing all records atomically.
    with transaction.atomic():
        current = NativeInvoice.objects.select_for_update().select_related(
            "order", "product"
        ).get(pk=invoice_id)
        current_order = current.order
        if current.status != NativeInvoice.Status.AWAITING:
            raise SettlementRejected("Invoice status changed while verifying")
        # Validate lock-time state and ensure the validated quote was not swapped.
        _validate(current)
        unchanged_fields = (
            "order_id", "customer_id", "asset", "network",
            "merchant_address", "verified_sender_address", "amount_atomic",
            "usd_amount", "issued_at", "expires_at", "wallet_challenge_id",
            "price_source", "price_observed_at", "usd_per_asset",
        )
        if any(getattr(invoice, f) != getattr(current, f) for f in unchanged_fields):
            raise SettlementRejected("Invoice changed after blockchain check")
        normalized_proof = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
        NativeChainTransfer.objects.create(
            invoice=current,
            network=current.network,
            tx_hash=normalized_hash,
            sender_address=current.verified_sender_address,
            recipient_address=current.merchant_address,
            amount_atomic=current.amount_atomic,
            verified_at=timezone.now(),
            verification_backend=backend,
            evidence_digest=hashlib.sha256(normalized_proof).hexdigest(),
        )
        ledger_ref=f"native-crypto:{current.network}:{normalized_hash}"
        LedgerEntry.objects.create(
            order=current_order, payment_intent=None, entry_type="payment",
            amount=PRICE_USD, currency="USD", reference=ledger_ref,
            metadata={
                "native_invoice_id": current.pk,
                "network": current.network, "asset": current.asset,
                "tx_hash": normalized_hash,
                "evidence_digest": hashlib.sha256(normalized_proof).hexdigest(),
            },
        )
        current.status=NativeInvoice.Status.PAID
        current.save(update_fields=["status", "updated_at"])
        # The order remains payment-pending until after both chain claim and
        # accounting entry are atomically durable in the same transaction.
        current_order.status="paid"
        current_order.save(update_fields=["status", "updated_at"])
    return "paid"


def reconcile_discovered_transfers(candidate_stream, *, ethereum_rpc=None, tron_solidity_rpc=None):
    """Bounded driver for a trusted backend transaction indexer.

    candidate_stream yields (invoice_id, tx_hash) from a SERVER-CONFIGURED
    indexer; never expose this iterable directly to customers. Suitable for
    invoking from a future scheduled command after safety review.
    """
    results = []
    for i, (invoice_id, tx_hash) in enumerate(candidate_stream):
        if i >= 100:
            break
        try:
            status = settle_native_invoice(
                invoice_id, tx_hash,
                ethereum_rpc=ethereum_rpc,
                tron_solidity_rpc=tron_solidity_rpc,
            )
        except (SettlementRejected, VerificationError, IntegrityError, ValueError):
            status = "not_settled"
        results.append((invoice_id, status))
    return results
