"""Trusted server-only generalized ETH/TRX invoice reservation.

The checkout integration must supply an independently verified buyer-sender
challenge and trusted price quote. This module is never exposed as an HTTP
endpoint. No merchant-wallet signature or per-sale approval is necessary.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from core.models import Order

from .models import CommerceInvoice
from .policy import CommercePolicyError, order_snapshot

RECEIVERS={
    "ETH": ("ethereum-mainnet","0x89149b01f59115B86553561F12438D2ADF517E75",18),
    "TRX": ("tron-mainnet","THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",6),
}


class InvoiceRejected(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedBuyer:
    sender: str
    challenge_id: str
    verified_at: object


@dataclass(frozen=True)
class TrustedRate:
    usd_per_asset: Decimal
    source: str
    observed_at: object


def reserve_order_invoice(order_id,asset,*,buyer,quote,now=None):
    if getattr(settings,"MPW_COMMERCE_INVOICING_ENABLED",False) is not True:
        raise InvoiceRejected("Sitewide checkout not released")
    if type(order_id) is not int or order_id<=0 or type(asset) is not str or asset not in RECEIVERS:
        raise InvoiceRejected("Invalid order/asset")
    if not isinstance(buyer,VerifiedBuyer) or not isinstance(quote,TrustedRate):
        raise InvoiceRejected("Verified buyer and server-side quote are mandatory")
    now=now if now is not None else timezone.now()
    if type(now) is not datetime or timezone.is_naive(now):
        raise InvoiceRejected("Trusted quote clock must be timezone aware")
    network,recipient,decimals=RECEIVERS[asset]
    address=buyer.sender
    if (type(address) is not str or type(buyer.challenge_id) is not str
            or not 8 <= len(buyer.challenge_id) <= 128
            or any(not 33 <= ord(ch) <= 126 for ch in buyer.challenge_id)):
        raise InvoiceRejected("Buyer wallet identity missing")
    if asset=="ETH":
        if re.fullmatch(r"0x[0-9a-fA-F]{40}",address) is None:
            raise InvoiceRejected("Invalid ETH sender")
    else:
        from scripts.mojplaywin_native_chain_verify import tron_address_to_hex, VerificationError
        try:
            tron_address_to_hex(address)
        except (VerificationError,TypeError) as exc:
            raise InvoiceRejected("Invalid TRX sender") from exc
    if (type(buyer.verified_at) is not datetime
        or timezone.is_naive(buyer.verified_at)
        or not timedelta(0)<=now-buyer.verified_at<=timedelta(minutes=5)):
        raise InvoiceRejected("Expired buyer-sender challenge")
    if (type(quote.source) is not str
        or quote.source not in ("coingecko","coinbase")
        or type(quote.observed_at) is not datetime
        or timezone.is_naive(quote.observed_at)
        or not timedelta(0)<=now-quote.observed_at<=timedelta(seconds=90)):
        raise InvoiceRejected("Invalid server price source or stale quote")
    # Never silently convert a float into an authoritative money quote.
    # The trusted price adapter must supply its exact Decimal representation.
    rate = quote.usd_per_asset
    if type(rate) is not Decimal or not rate.is_finite() or rate <= 0:
        raise InvoiceRejected("Invalid trusted Decimal quote")
    # CommerceInvoice.quote_usd_per_asset is decimal(30,12). Rounding a
    # trusted rate during save must never change the customer invoice amount.
    try:
        if (rate >= Decimal("1e18")
                or rate != rate.quantize(Decimal("0.000000000001"))):
            raise InvoiceRejected("Quote exceeds immutable database precision")
    except (ArithmeticError, ValueError) as exc:
        raise InvoiceRejected("Quote cannot be represented exactly") from exc
    with transaction.atomic():
        order=(Order.objects.select_for_update()
               .select_related("customer").filter(pk=order_id).first())
        if order is None:
            raise InvoiceRejected("Unknown order")
        try:
            total,_=order_snapshot(order)
        except CommercePolicyError as exc:
            raise InvoiceRejected(str(exc)) from exc
        if CommerceInvoice.objects.filter(order=order).exists():
            raise InvoiceRejected("Order already has a locked invoice")
        atomic=(total/rate*Decimal(10)**decimals).to_integral_value(
            rounding=ROUND_CEILING)
        amount=int(atomic)
        if amount<=0 or len(str(amount))>50:
            raise InvoiceRejected("Unrepresentable smallest-unit amount")
        # Two independent orders may have the same final price. A verified
        # blockchain transaction is unique by (network, tx_hash), and its
        # sender, recipient, exact amount, finality and order binding are all
        # revalidated at settlement. Never add random micro-amounts.
        return CommerceInvoice.objects.create(
            order=order,asset=asset,network=network,recipient=recipient,
            expected_sender=address,amount_atomic=str(amount),total_usd=total,
            quote_usd_per_asset=rate,quote_source=quote.source,
            quote_observed_at=quote.observed_at,
            sender_challenge_id=buyer.challenge_id,
            sender_signature_verified_at=buyer.verified_at,
            issued_at=now,expires_at=now+timedelta(minutes=10),
        )
