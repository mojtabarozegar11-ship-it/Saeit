"""Plan 1 prospective customer contact records, NOT paid challenge enrollments."""
from django.core.exceptions import ValidationError
from django.db import models
from core.consent_guard_queryset import ConsentStatusQuerySet

class PropInterest(models.Model):
    """Consent-only sales inquiry. Never creates invoices, entitlements or trades."""
    objects = ConsentStatusQuerySet.as_manager()
    email = models.EmailField(max_length=254, unique=True)
    plan_code = models.CharField(max_length=16, default="MOJ-PROP-01")
    consent_version = models.CharField(max_length=40, default="moj-prop-interest-v1")
    source_language = models.CharField(max_length=8, default="en")
    status = models.CharField(
        max_length=16, default="new",
        choices=(("new", "New"), ("contacted", "Contacted"),
                 ("withdrawn", "Consent withdrawn")),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=("status", "-created_at"), name="mp_interest_status")]

    def _check_withdrawal_lock(self):
        # Never rewrite the email/provenance that an original consent covers:
        # otherwise withdrawal could be hidden by changing the old identity.
        if self.pk is None:
            return
        identity = ("email", "plan_code", "consent_version", "source_language")
        original = type(self).objects.filter(pk=self.pk).values("status", *identity).first()
        if original is None:
            return
        if original["status"] == "withdrawn" and self.status != "withdrawn":
            raise ValidationError({"status": "Withdrawn consent cannot be reactivated"})
        for field in identity:
            if getattr(self, field) != original[field]:
                raise ValidationError({field: "Consent identity and origin cannot be rewritten"})

    def clean(self):
        super().clean()
        self._check_withdrawal_lock()

    def save(self, *args, **kwargs):
        self._check_withdrawal_lock()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"moj-prop-interest:{self.pk}"
