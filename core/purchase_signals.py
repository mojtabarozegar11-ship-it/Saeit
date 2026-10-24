"""Payment-event subscriber; no cron or direct access-control changes."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Order, PaymentWebhookEvent
from core.purchase_event import schedule_paid_order_review, schedule_paid_purchase_review


@receiver(post_save, sender=Order, dispatch_uid="saeit_paid_purchase_operating_v1")
def on_paid_order_saved(sender, instance, created, update_fields, using, **kwargs):
    if using != "default" or instance.status != "paid":
        return
    if update_fields is not None and "status" not in update_fields:
        return
    schedule_paid_order_review(instance.pk, using=using)


@receiver(
    post_save,
    sender=PaymentWebhookEvent,
    dispatch_uid="saeit_settled_payment_business_v1",
)
def on_processed_payment_receipt(sender, instance, created, update_fields, using, **kwargs):
    if (using != "default" or instance.status != "processed"
            or instance.event_type not in {"payment.succeeded", "tron_finalized"}
            or not instance.payment_intent_id):
        return
    if update_fields is not None and "status" not in update_fields:
        return
    schedule_paid_purchase_review(
        instance.payment_intent_id,
        provider=instance.provider,
        event_id=instance.event_id,
    )
