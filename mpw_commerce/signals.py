"""Evidence-backed identity projections for commerce records."""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import GuestOrderEmail, LedgerEntry

from .buyer_identity import record_buyer_identity


@receiver(post_save, sender=GuestOrderEmail)
def project_checkout_email(sender, instance, created, **kwargs):
    if not created:
        return
    record_buyer_identity(
        order=instance.order,
        email=instance.email_address,
        source="checkout_email",
    )


@receiver(post_save, sender=LedgerEntry)
def project_verified_wallet(sender, instance, created, **kwargs):
    if not created or instance.entry_type != "credit":
        return
    metadata = instance.metadata if isinstance(instance.metadata, dict) else {}
    payer_wallet = metadata.get("sender")
    network = metadata.get("network", "")
    tx_hash = metadata.get("tx_hash", "")
    if not isinstance(payer_wallet, str) or not payer_wallet:
        return
    if not isinstance(network, str) or not isinstance(tx_hash, str):
        return
    record_buyer_identity(
        order=instance.order,
        payer_wallet=payer_wallet,
        network=network,
        tx_hash=tx_hash,
        source="verified_tron_receipt",
        verified_at=instance.created_at,
    )
