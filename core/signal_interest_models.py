"""One canonical non-billing CRM for MOJ PROP and Mojtaba.bot.ai signals."""
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


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
    withdrawn_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("email", "offer_family", "brand", "plan_code", "source_host"),
                name="core_comint_host_key",
            ),
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
        """Preserve the original consent and make withdrawal terminal, even in concurrent writes.

        ORM bulk update is intentionally not offered through the operator interface.
        """
        provenance = (
            "email", "offer_family", "brand", "plan_code", "consent_version",
            "source_language", "source_host",
        )
        with transaction.atomic():
            previous = None
            if self.pk is not None:
                previous = type(self).objects.select_for_update().filter(pk=self.pk).first()
            if previous is not None:
                for field in provenance:
                    if getattr(previous, field) != getattr(self, field):
                        raise ValidationError({field: "Original consent evidence is immutable"})
                if previous.status == "withdrawn" and self.status != "withdrawn":
                    raise ValidationError({"status": "Withdrawn contact consent cannot be reactivated"})
                if previous.withdrawn_at is not None:
                    self.withdrawn_at = previous.withdrawn_at
                elif self.status == "withdrawn":
                    self.withdrawn_at = timezone.now()
            elif self.status == "withdrawn":
                self.withdrawn_at = timezone.now()
            if self.status != "withdrawn" and self.withdrawn_at is not None:
                raise ValidationError({"withdrawn_at": "Withdrawal timestamp requires withdrawn status"})
            fields = kwargs.get("update_fields")
            if fields is not None and previous is not None and self.status != previous.status and "status" not in fields:
                raise ValidationError({"status": "Status transitions must be saved explicitly"})
            if fields is not None and self.status == "withdrawn":
                kwargs["update_fields"] = set(fields) | {"withdrawn_at"}
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"commercial-interest:{self.offer_family}:{self.pk}"

# Source-compatibility alias for existing canonical signal-interest code.
SignalInterest = CommercialInterest
