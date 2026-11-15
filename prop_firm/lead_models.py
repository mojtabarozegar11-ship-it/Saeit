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
        # A withdrawn lead must never become contactable again through
        # ordinary admin edits or model.save(). A new opt-in needs a separate
        # verified consent lifecycle, not an undocumented status reset.
        if (self.pk is not None and self.status != "withdrawn"
                and type(self).objects.filter(pk=self.pk, status="withdrawn").exists()):
            raise ValidationError({"status": "Withdrawn consent cannot be reactivated"})

    def clean(self):
        super().clean()
        self._check_withdrawal_lock()

    def save(self, *args, **kwargs):
        self._check_withdrawal_lock()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"moj-prop-interest:{self.pk}"
