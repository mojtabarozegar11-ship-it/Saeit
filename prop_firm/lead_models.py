"""Plan 1 prospective customer contact records, NOT paid challenge enrollments."""
from django.core.exceptions import ValidationError
from django.db import models, transaction
from .consent_guard_queryset import ConsentStatusQuerySet

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

    def _check_withdrawal_lock(self, *, lock=False):
        # Original consent provenance and a later opt-out are terminal.
        # A plain read before save is subject to a concurrent withdrawal:
        # check the current row FOR UPDATE in the *same* transaction as save.
        if self.pk is None:
            return
        identity = ("email", "plan_code", "consent_version", "source_language")
        query = type(self).objects.filter(pk=self.pk)
        if lock:
            query = query.select_for_update()
        original = query.values("status", *identity).first()
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
        # Serialize operator follow-ups and revocation against each other.
        # The lock must remain held until after Django writes the new state;
        # other backends' bulk withdrawal must not race this saved instance.
        # No checkout, invoice, notification or broker side effect.
        with transaction.atomic():
            self._check_withdrawal_lock(lock=True)
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"moj-prop-interest:{self.pk}"
