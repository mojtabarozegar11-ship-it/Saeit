"""Payment-event subscriber; no cron or direct access-control changes."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Order
from core.purchase_event import schedule_paid_order_review


@receiver(post_save, sender=Order, dispatch_uid="saeit_paid_purchase_operating_v1")
def on_paid_order_saved(sender, instance, created, update_fields, using, **kwargs):
    if instance.status != "paid":
        return
    if update_fields is not None and "status" not in update_fields:
        return
    schedule_paid_order_review(instance.pk, using=using)
