"""One canonical non-billing CRM for MOJ PROP and Mojtaba.bot.ai signals."""
from django.core.exceptions import ValidationError
from django.db import models


class CommercialInterest(models.Model):
    """A genuine enquiry; creating this row NEVER charges a card or wallet."""
    email = models.EmailField(max_length=254)
    offer_family = models.CharField(max_length=16, default="signals", choices=(
        ("signals", "Market signal information"),
        ("moj_prop", "MOJ PROP Plan 1 information"),
    ))
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
            models.UniqueConstraint(fields=("email", "offer_family", "brand", "plan_code"),
                                    name="core_commercial_interest_key"),
        ]
        indexes = [
            models.Index(fields=("status", "-created_at"),
                         name="core_signal_interest_status"),
        ]

    def clean(self):
        from .signal_interest_policy import SIGNAL_BRANDS, SUPPORTED_LOCALES, SIGNAL_PLAN_CODES
        if self.offer_family == "signals":
            if self.brand not in SIGNAL_BRANDS:
                raise ValidationError({"brand": "Unknown signal brand"})
            if self.plan_code not in SIGNAL_PLAN_CODES:
                raise ValidationError({"plan_code": "Unknown signal package"})
            if self.source_language not in SUPPORTED_LOCALES:
                raise ValidationError({"source_language": "Unknown signal language"})
            if self.source_host not in (
                "mojplaywin.com", "www.mojplaywin.com",
                "zomorodmelal.ir", "www.zomorodmelal.ir",
            ):
                raise ValidationError({"source_host": "Unknown signal host"})
            if self.consent_version != "mojtaba-signals-interest-v1":
                raise ValidationError({"consent_version": "Signal contact consent required"})
        elif self.offer_family == "moj_prop":
            if self.brand != "moj_prop" or self.plan_code != "MOJ-PROP-01":
                raise ValidationError("Only the first MOJ PROP information request is available")
            if self.source_host not in ("mojplaywin.com", "www.mojplaywin.com"):
                raise ValidationError({"source_host": "MOJ PROP is MojPlayWin-only"})
            if self.source_language not in ("en", "fa", "ar", "de"):
                raise ValidationError({"source_language": "Unsupported MOJ PROP language"})
            if self.consent_version != "moj-prop-interest-v1":
                raise ValidationError({"consent_version": "MOJ PROP contact consent required"})
        else:
            raise ValidationError({"offer_family": "Unknown service family"})
        from django.core.validators import validate_email
        validate_email(self.email)
        if self.email != self.email.strip().lower():
            raise ValidationError({"email": "Canonical lower-case email required"})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"commercial-interest:{self.offer_family}:{self.pk}"

# Source-compatibility alias for existing canonical signal-interest code.
SignalInterest = CommercialInterest
