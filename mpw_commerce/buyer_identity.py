"""Durable, staff-only buyer identity projection for paid commerce orders.

Email is accepted only from the checkout claim. Wallet data is accepted only
from an independently verified settlement. This module never authorizes
payment, delivery, email sending or wallet transfers.
"""
from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .models import CommerceBuyerIdentity


class BuyerIdentityConflict(ValueError):
    """Existing verified identity data may not be silently replaced."""


def _email(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 254:
        raise ValueError("Invalid buyer email")
    value = value.strip().casefold()
    try:
        validate_email(value)
    except ValidationError as exc:
        raise ValueError("Invalid buyer email") from exc
    return value


def _email_digest(value: str) -> str:
    return hmac.new(
        str(settings.SECRET_KEY).encode("utf-8"),
        ("mpw:buyer-identity:email:" + value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def record_buyer_identity(
    *,
    order,
    email=None,
    payer_wallet=None,
    network="",
    tx_hash="",
    source="",
    verified_at=None,
):
    """Create or complete one order identity using verified evidence only."""
    if getattr(order, "pk", None) is None:
        raise ValueError("Persisted order is required")
    if email is None and payer_wallet is None:
        raise ValueError("At least one verified identity field is required")
    if email is not None:
        email = _email(email)
        email_digest = _email_digest(email)
    else:
        email_digest = ""
    if payer_wallet is not None:
        if (not isinstance(payer_wallet, str) or not payer_wallet.strip()
                or len(payer_wallet.strip()) > 100):
            raise ValueError("Invalid payer wallet")
        payer_wallet = payer_wallet.strip()
    if not isinstance(network, str) or len(network) > 32:
        raise ValueError("Invalid network")
    if not isinstance(tx_hash, str) or len(tx_hash) > 80:
        raise ValueError("Invalid transaction hash")
    if not isinstance(source, str) or len(source) > 32:
        raise ValueError("Invalid identity source")

    with transaction.atomic():
        identity, _ = CommerceBuyerIdentity.objects.select_for_update().get_or_create(
            order=order
        )
        updates = []
        if email is not None:
            if identity.email_address and identity.email_address != email:
                raise BuyerIdentityConflict("Buyer email cannot be reassigned")
            if not identity.email_address:
                identity.email_address = email
                identity.email_digest = email_digest
                updates += ["email_address", "email_digest"]
        if payer_wallet is not None:
            if identity.payer_wallet and identity.payer_wallet != payer_wallet:
                raise BuyerIdentityConflict("Payer wallet cannot be reassigned")
            if not identity.payer_wallet:
                identity.payer_wallet = payer_wallet
                updates.append("payer_wallet")
        if network and not identity.network:
            identity.network = network
            updates.append("network")
        if tx_hash and not identity.tx_hash:
            identity.tx_hash = tx_hash
            updates.append("tx_hash")
        if source and not identity.source:
            identity.source = source
            updates.append("source")
        if verified_at is not None:
            if identity.verified_at is None:
                identity.verified_at = verified_at
                updates.append("verified_at")
        elif payer_wallet is not None and identity.verified_at is None:
            identity.verified_at = timezone.now()
            updates.append("verified_at")
        if updates:
            identity.save(update_fields=updates + ["updated_at"])
        return identity
