"""One-time buyer ETH/TRX signed-text wallet linkage and invoice reservation.

This is ONLY to identify the paying customer wallet for a cart. The merchant
does not sign or approve orders. Only the user's own signed text is accepted;
no spending approval, wallet keys, network transfers or blockchain writes.

No route is connected to the live site. All gates default to disabled.
"""
from datetime import datetime,timedelta,timezone as utc_timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import secrets
import subprocess

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Order
from .models import BuyerWalletChallenge
from .invoicing import (
    RECEIVERS, VerifiedBuyer,TrustedRate,reserve_order_invoice,
)
from .policy import order_snapshot,CommercePolicyError

MAX_CHALLENGES_PER_10_MINUTES=6
CHALLENGE_LIFETIME=timedelta(minutes=5)


class WalletLinkRejected(ValueError):
    pass


def _buyer_id(buyer):
    if (not getattr(buyer,"is_authenticated",False) or
        not getattr(buyer,"is_active",False) or
        type(getattr(buyer,"pk",None)) is not int):
        raise WalletLinkRejected("Authenticated active buyer required")
    return buyer.pk


def _canonical_address(asset,address):
    if type(asset) is not str or asset not in RECEIVERS or not isinstance(address,str):
        raise WalletLinkRejected("Unrecognized payment network or wallet")
    if asset=="ETH":
        if re.fullmatch(r"0x[a-fA-F0-9]{40}",address) is None:
            raise WalletLinkRejected("Invalid ETH wallet")
        return address
    from scripts.mojplaywin_native_chain_verify import (
        tron_address_to_hex,VerificationError,
    )
    try:
        tron_address_to_hex(address)
    except (VerificationError,ValueError,TypeError) as exc:
        raise WalletLinkRejected("Invalid TRON wallet") from exc
    return address


def challenge_message(entry):
    if (not isinstance(entry,BuyerWalletChallenge) or
        entry.asset not in RECEIVERS):
        raise WalletLinkRejected("Invalid buyer challenge")
    return "\n".join((
        "MojPlayWin Customer Wallet Link",
        "Domain: mojplaywin.com",
        "Purpose: Verify customer wallet ONLY for checkout.",
        "This signature does NOT authorize transfers, spending or token allowances.",
        "Network: "+RECEIVERS[entry.asset][0],
        "Address: "+entry.sender_address,
        "Order ID: "+str(entry.order_id),
        "Customer ID: "+str(entry.customer_id),
        "Challenge ID: "+str(entry.pk),
        "Nonce: "+entry.nonce,
        "Issued UTC: "+str(int(entry.issued_at.timestamp())),
        "Expires UTC: "+str(int(entry.expires_at.timestamp())),
    ))


def issue_buyer_wallet_challenge(order_id,buyer,asset,address,*,now=None):
    if getattr(settings,"MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",False) is not True:
        raise WalletLinkRejected("Buyer wallet verification is disabled")
    customer_id=_buyer_id(buyer)
    if type(order_id) is not int or order_id<=0:
        raise WalletLinkRejected("Invalid order identifier")
    address=_canonical_address(asset,address)
    now=now or timezone.now()
    order=Order.objects.select_related("customer").filter(
        pk=order_id,customer_id=customer_id,status="pending",
    ).first()
    if order is None:
        raise WalletLinkRejected("Order does not belong to buyer")
    try:
        order_snapshot(order)
    except CommercePolicyError as exc:
        raise WalletLinkRejected("Order is not eligible for checkout") from exc
    with transaction.atomic():
        if BuyerWalletChallenge.objects.filter(
            customer_id=customer_id,issued_at__gte=now-timedelta(minutes=10)
        ).count()>=MAX_CHALLENGES_PER_10_MINUTES:
            raise WalletLinkRejected("Too many wallet challenges")
        challenge=BuyerWalletChallenge.objects.create(
            order=order,customer_id=customer_id,asset=asset,
            sender_address=address,nonce=secrets.token_urlsafe(24),
            issued_at=now,expires_at=now+CHALLENGE_LIFETIME,
        )
    return challenge,challenge_message(challenge)


def verify_signed_buyer_message(entry,signature):
    """Launch the preinstalled isolated, read-only crypto verifier process."""
    python_path=getattr(settings,"MPW_COMMERCE_BUYER_CRYPTO_PYTHON","")
    worker=Path(__file__).with_name("buyer_signature_worker.py")
    if (not isinstance(python_path,str) or not python_path.startswith("/")
        or not Path(python_path).is_file() or Path(python_path).is_symlink()
        or not worker.is_file() or worker.is_symlink()
        or not isinstance(signature,str) or len(signature)>140):
        raise WalletLinkRejected("Buyer signature verifier unavailable")
    payload=json.dumps({
        "asset":entry.asset,
        "address":entry.sender_address,
        "message":challenge_message(entry),
        "signature":signature,
    },separators=(",",":")).encode("utf-8")
    try:
        proc=subprocess.run(
            [python_path,"-I",str(worker)],
            input=payload,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=7,check=False,
            env={"PATH":"/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1"},
        )
        if proc.returncode!=0 or len(proc.stdout)>128:
            return False
        return json.loads(proc.stdout.decode("ascii"))=={"verified":True}
    except (OSError,subprocess.TimeoutExpired,ValueError,UnicodeError) as exc:
        raise WalletLinkRejected("Signature verification unavailable") from exc


def submit_buyer_wallet_signature(
    buyer,challenge_id,signature,*,now=None,verifier=verify_signed_buyer_message,
):
    """Valid signer attested once, invalid signatures limited to 4 attempts."""
    if getattr(settings,"MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",False) is not True:
        raise WalletLinkRejected("Buyer verification is disabled")
    user_id=_buyer_id(buyer)
    if type(challenge_id) is not int or challenge_id<=0:
        raise WalletLinkRejected("Invalid challenge")
    now=now or timezone.now()
    with transaction.atomic():
        entry=BuyerWalletChallenge.objects.select_for_update().filter(
            pk=challenge_id,customer_id=user_id,
        ).first()
        if (entry is None or entry.used_at is not None
            or entry.verified_at is not None
            or now<entry.issued_at or now>=entry.expires_at
            or entry.failed_attempts>=4):
            raise WalletLinkRejected("Challenge unavailable or expired")
        valid=False
        try:
            valid=verifier(entry,signature) is True
        except (WalletLinkRejected,TypeError,ValueError):
            valid=False
        if not valid:
            entry.failed_attempts+=1
            entry.save(update_fields=["failed_attempts"])
            return False
        entry.verified_at=now
        entry.save(update_fields=["verified_at"])
        return True


def fetch_server_rate(asset,*,now=None):
    """Only this server-side function may supply the price for a buyer invoice."""
    if type(asset) is not str or asset not in RECEIVERS:
        raise WalletLinkRejected("Unsupported currency")
    from scripts.mojplaywin_direct_wallet_rates import (
        fetch_fresh_rates,RateFeedUnavailable,
    )
    try:
        snap=fetch_fresh_rates()
        item=snap[asset]
        observed=datetime.fromtimestamp(item.observed_at_epoch,utc_timezone.utc)
        return TrustedRate(
            usd_per_asset=Decimal(item.usd_per_asset),
            source=item.provider,
            observed_at=observed,
        )
    except (RateFeedUnavailable,KeyError,ValueError,TypeError) as exc:
        raise WalletLinkRejected("Trusted server rate unavailable") from exc


def invoice_from_verified_buyer(buyer,challenge_id,*,now=None,rate_loader=fetch_server_rate):
    """Consume one signed wallet challenge to create one unique order invoice.

    A browser must NOT provide an exchange rate, quote or a merchant approval.
    Caller authentication, signature validation and price are server-owned.
    """
    if getattr(settings,"MPW_COMMERCE_INVOICING_ENABLED",False) is not True:
        raise WalletLinkRejected("Automatic checkout disabled")
    buyer_id=_buyer_id(buyer)
    if type(challenge_id) is not int or challenge_id<=0:
        raise WalletLinkRejected("Invalid challenge identifier")
    now=now or timezone.now()
    with transaction.atomic():
        entry=BuyerWalletChallenge.objects.select_for_update().filter(
            pk=challenge_id,customer_id=buyer_id,
        ).first()
        if (entry is None or entry.used_at is not None
            or entry.verified_at is None
            or now<entry.issued_at or now>=entry.expires_at
            or now-entry.verified_at>timedelta(minutes=5)):
            raise WalletLinkRejected("A fresh verified wallet signature is required")
        rate=rate_loader(entry.asset)
        invoice=reserve_order_invoice(
            entry.order_id,entry.asset,
            buyer=VerifiedBuyer(
                sender=entry.sender_address,challenge_id=str(entry.nonce),
                verified_at=entry.verified_at,
            ),
            quote=rate,now=now,
        )
        entry.used_at=now
        entry.save(update_fields=["used_at"])
        return invoice
