"""One canonical opt-in CRM for Mojtaba.bot.ai signal interest, not subscriptions."""
from django.core.exceptions import ValidationError
from django.db import models


class SignalInterest(models.Model):
    """A genuine enquiry; creating this row NEVER charges a card or wallet."""
    email = models.EmailField(max_length=254)
    brand = models.CharField(max_length=24)
    plan_code = models.CharField(max_length=40)
    consent_version = models.CharField(max_length=40, default="mojtaba-signals-interest-v1")
    source_language = models.CharField(max_length=2, default="en")
    source_host = models.CharField(max_length=100)
    status = models.CharField(max_length=16, default="new", choices=(
        ("new", "New"), ("contacted", "Contacted"),
        ("withdrawn", "Consent withdrawn"),
    ))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("email", "brand", "plan_code"),
                                    name="core_signal_interest_per_plan"),
        ]
        indexes = [
            models.Index(fields=("status", "-created_at"),
                         name="core_signal_interest_status"),
        ]

    def clean(self):
        from .signal_commercial_catalog import SIGNAL_BRANDS, SUPPORTED_LOCALES
        from .signal_product_plans import SIGNAL_PLANS
        if self.brand not in SIGNAL_BRANDS:
            raise ValidationError({"brand": "Unknown branded origin"})
        if self.plan_code not in {p.sku for p in SIGNAL_PLANS}:
            raise ValidationError({"plan_code": "Unknown signal interest plan"})
        if self.source_language not in SUPPORTED_LOCALES:
            raise ValidationError({"source_language": "Unsupported language"})
        if self.source_host not in (
            "mojplaywin.com", "www.mojplaywin.com",
            "zomorodmelal.ir", "www.zomorodmelal.ir",
        ):
            raise ValidationError({"source_host": "Unknown source host"})
        if self.consent_version != "mojtaba-signals-interest-v1":
            raise ValidationError({"consent_version": "Unapproved consent"})
        from django.core.validators import validate_email
        validate_email(self.email)
        if self.email != self.email.strip().lower():
            raise ValidationError({"email": "Canonical lower-case email required"})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"signal-interest:{self.pk}"
