"""Plan 1 prospective customer contact records, NOT paid challenge enrollments."""
from django.db import models

class PropInterest(models.Model):
    """Consent-only sales inquiry. Never creates invoices, entitlements or trades."""
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

    class Meta:
        indexes = [models.Index(fields=("status", "-created_at"), name="mp_interest_status")]
    
    def __str__(self):
        return f"moj-prop-interest:{self.pk}"
