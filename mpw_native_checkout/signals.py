"""Native-coin checkout emits events only AFTER the DB transaction commits."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import NativeInvoice
from .purchase_notify import notify_after_commit


@receiver(post_save, sender=NativeInvoice, dispatch_uid="mpw_native_checkout_invoice_events_v1")
def on_native_invoice_change(sender, instance, created, update_fields=None, **kwargs):
    if instance.product_id != 72:
        return
    if created and instance.status == NativeInvoice.Status.AWAITING:
        # Legacy route requires previously signed wallet proof and buyer proof;
        # all new purchases use the separate mpw_commerce engine instead.
        if (instance.sender_signature_verified_at is not None
                and instance.merchant_ownership_verified_at is not None):
            notify_after_commit(instance, "invoice_open")
    elif not created and instance.status in (
        NativeInvoice.Status.PAID,
        NativeInvoice.Status.EXPIRED,
        NativeInvoice.Status.REFUND_REVIEW,
    ):
        if update_fields is None or "status" in update_fields:
            notify_after_commit(instance, "invoice_closed")
