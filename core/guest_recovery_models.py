"""Minimal, durable ownership proof for MojPlayWin guest TRX orders.

Neither an unverified payment nor an old guest browser cookie is evidence of
email ownership.  Historical orders deliberately have no GuestOrderEmail.
"""
from django.core.exceptions import ValidationError
from django.db import models


class GuestOrderEmail(models.Model):
    order = models.OneToOneField(
        "core.Order", on_delete=models.PROTECT, related_name="guest_email_claim"
    )
    email_address = models.EmailField(max_length=254)
    email_digest = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Verified-at-checkout guest order email"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            original = type(self).objects.filter(pk=self.pk).values(
                "order_id", "email_address", "email_digest"
            ).first()
            if original is not None and (
                original["order_id"] != self.order_id or
                original["email_address"] != self.email_address or
                original["email_digest"] != self.email_digest
            ):
                raise ValidationError("Checkout email cannot be reassigned")
        return super().save(*args, **kwargs)


class GuestRecoveryToken(models.Model):
    # The plaintext 256-bit recovery code is NEVER stored in the database.
    token_digest = models.CharField(max_length=64, unique=True)
    email_digest = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)


class GuestRecoveryRate(models.Model):
    # Per-IP and per-email HMAC buckets, with no raw IP or email recorded.
    bucket = models.CharField(max_length=64, unique=True)
    count = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
