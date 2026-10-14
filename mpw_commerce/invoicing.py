"""Trusted server-only generalized ETH/TRX invoice reservation.

The checkout integration must supply an independently verified buyer-sender
challenge and trusted price quote. This module is never exposed as an HTTP
endpoint. No merchant-wallet signature or per-sale approval is necessary.
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
import secrets
import re

from django.conf import settings
from django.db import transaction, IntegrityError
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
    now=now or timezone.now()
    network,recipient,decimals=RECEIVERS[asset]
    address=buyer.sender
    if not isinstance(address,str) or not isinstance(buyer.challenge_id,str) or not 8<=len(buyer.challenge_id)<=128:
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
    if (not buyer.verified_at or timezone.is_naive(buyer.verified_at)
        or not timedelta(0)<=now-buyer.verified_at<=timedelta(minutes=5)):
        raise InvoiceRejected("Expired buyer-sender challenge")
    if (quote.source not in ("coingecko","coinbase")
        or not quote.observed_at or timezone.is_naive(quote.observed_at)
        or not timedelta(0)<=now-quote.observed_at<=timedelta(seconds=90)):
        raise InvoiceRejected("Invalid server price source or stale quote")
    try:
        rate=Decimal(str(quote.usd_per_asset))
        if not rate.is_finite() or rate<=0:
            raise ValueError()
    except (InvalidOperation,ValueError):
        raise InvoiceRejected("Invalid quote")
    with transaction.atomic():
        order=(Order.objects.select_for_update()
               .select_related("customer").get(pk=order_id))
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
        # Every invoice has one unique smallest-unit amount on the same receiver.
        # Otherwise two simultaneous purchases of the same priced item would
        # be indistinguishable. Bounded sub-cent native-coin adjustment is shown
        # to the buyer in the exact ETH/TRX quote, never hidden at settlement.
        max_extra=(Decimal("0.0049")/rate*Decimal(10)**decimals)
        maximum=min(100000,int(max_extra.to_integral_value(rounding=ROUND_FLOOR)))
        if maximum<1:
            raise InvoiceRejected("Quote cannot encode a distinct micro-amount")
        for attempt in range(24):
            smallest=str(amount+secrets.randbelow(maximum+1))
            if len(smallest)>50:
                raise InvoiceRejected("Quote smallest-unit text too long")
            if CommerceInvoice.objects.filter(
                network=network,recipient=recipient,amount_atomic=smallest
            ).exists():
                continue
            try:
                with transaction.atomic():
                    return CommerceInvoice.objects.create(
                        order=order,asset=asset,network=network,recipient=recipient,
                        expected_sender=address,amount_atomic=smallest,total_usd=total,
                        quote_usd_per_asset=rate,quote_source=quote.source,
                        quote_observed_at=quote.observed_at,
                        sender_challenge_id=buyer.challenge_id,
                        sender_signature_verified_at=buyer.verified_at,
                        issued_at=now,expires_at=now+timedelta(minutes=10),
                    )
            except IntegrityError:
                continue
        raise InvoiceRejected("No unique exact-amount quote available; retry later")
