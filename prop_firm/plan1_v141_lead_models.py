"""Separate, contact-only v1.4.1 MOJ-PROP-01 enquiries.

No purchase, contract acceptance, financial marketing opt-in, brokerage order,
payment, payout or entitlement is possible through this table. Historical
PropInterest consent stays unchanged. An opted-out address is never revived.
"""
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.consent_guard_queryset import ConsentStatusQuerySet


CONSENT_VERSION = "moj-prop-v141-info-contact-v1"


class PropV141Interest(models.Model):
    objects = ConsentStatusQuerySet.as_manager()
    email = models.EmailField(max_length=254, unique=True)
    plan_code = models.CharField(max_length=16, default="MOJ-PROP-01")
    consent_version = models.CharField(max_length=48, default=CONSENT_VERSION)
    source_language = models.CharField(max_length=2, default="en")
    status = models.CharField(
        max_length=16,
        choices=(("new", "New"), ("contacted", "Contacted"),
                 ("withdrawn", "Consent withdrawn")),
        default="new",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("status", "-created_at"),
                         name="mp_v141_interest_st"),
        ]

    def _verify_original(self, *, lock=False):
        if self.pk is None:
            return
        original_qs = type(self).objects.filter(pk=self.pk)
        if lock:
            original_qs = original_qs.select_for_update()
        original = original_qs.values(
            "status", "email", "plan_code",
            "consent_version", "source_language",
        ).first()
        if original is None:
            return
        if original["status"] == "withdrawn" and self.status != "withdrawn":
            raise ValidationError({"status": "Withdrawn contact consent is final"})
        for field in ("email", "plan_code", "consent_version", "source_language"):
            if getattr(self, field) != original[field]:
                raise ValidationError({field: "The consent origin is immutable"})

    def clean(self):
        super().clean()
        if self.plan_code != "MOJ-PROP-01" or self.consent_version != CONSENT_VERSION:
            raise ValidationError("Only the isolated current Plan 1 inquiry is allowed")
        if self.source_language not in ("en", "fa"):
            raise ValidationError("Unsupported inquiry language")
        self._verify_original()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self._verify_original(lock=True)
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"moj-prop-v141-interest:{self.pk}"
