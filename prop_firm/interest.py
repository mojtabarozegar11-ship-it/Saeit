"""Opt-in interest intake for the MojPlayWin Moj Prop information page.

Not an application, KYC request, challenge enrollment, trading account,
payment authorization, regulated marketing campaign or permission to email.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import hmac
import ipaddress

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .models import PropInformationInquiry


CONSENT_VERSION = "moj-prop-interest-2026-11-15-v1"
RETENTION_DAYS = 30
MAX_HOURLY_REQUESTS = 6
DISALLOWED_DOMAINS = frozenset({
    "example.com", "example.net", "example.org",
    "guest.mojplaywin.com", "localhost",
})


class PropInterestError(ValueError):
    pass


def canonical_inquiry_email(value):
    if (type(value) is not str or not 5 <= len(value) <= 254
            or not value.isascii() or value != value.strip()
            or value.count("@") != 1):
        raise PropInterestError("valid_contact_email_required")
    try:
        validate_email(value)
    except ValidationError as exc:
        raise PropInterestError("valid_contact_email_required") from exc
    local, domain = value.rsplit("@", 1)
    domain = domain.lower()
    if (domain in DISALLOWED_DOMAINS
            or domain.endswith((".invalid", ".test", ".example", ".local", ".localhost"))
            or ".." in local
            or local.startswith(".") or local.endswith(".")):
        raise PropInterestError("valid_contact_email_required")
    return local + "@" + domain


def _secret():
    key = getattr(settings, "MOJ_PROP_INTEREST_HMAC_KEY_HEX", "")
    if (type(key) is not str or len(key) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in key)
            or key.lower() == "0" * 64):
        raise PropInterestError("protected_interest_secret_required")
    return bytes.fromhex(key)


def _digest(value, secret):
    return hmac.new(secret, b"moj-prop-interest-v1\x00" + value.encode("ascii"), sha256).hexdigest()


def intake_enabled():
    return (
        getattr(settings, "MOJ_PROP_INTEREST_ENABLED", False) is True
        and getattr(settings, "MOJ_PROP_PRIVACY_URL", "") == "/privacy/"
        and len(getattr(settings, "MOJ_PROP_INTEREST_HMAC_KEY_HEX", "")) == 64
    )


def _rate_limit(ip, secret):
    try:
        canonical_ip = ipaddress.ip_address(ip).compressed
    except ValueError as exc:
        raise PropInterestError("invalid_request_origin") from exc
    # Do not persist the raw address in a lead table or log.
    hour = timezone.now().strftime("%Y%m%d%H")
    digest = _digest(hour + ":" + canonical_ip, secret)
    key = "mojprop:interest:" + digest
    try:
        if cache.add(key, 1, timeout=3600):
            return
        count = cache.incr(key)
        if count > MAX_HOURLY_REQUESTS:
            raise PropInterestError("interest_rate_limited")
    except PropInterestError:
        raise
    except Exception as exc:
        raise PropInterestError("interest_rate_check_unavailable") from exc


@transaction.atomic
def submit_inquiry(*, email, consent, remote_addr, now=None):
    """Store one nonfinancial information request only, without sending mail."""
    if not intake_enabled():
        raise PropInterestError("interest_intake_not_released")
    if consent is not True:
        raise PropInterestError("explicit_privacy_consent_required")
    secret = _secret()
    canonical = canonical_inquiry_email(email)
    _rate_limit(remote_addr, secret)
    timestamp = timezone.now() if now is None else now
    if timestamp.tzinfo is None:
        raise PropInterestError("timezone_aware_clock_required")
    digest = _digest(canonical, secret)
    row, created = PropInformationInquiry.objects.get_or_create(
        email_digest=digest,
        defaults={
            "email": canonical,
            "consent_version": CONSENT_VERSION,
            "expires_at": timestamp + timedelta(days=RETENTION_DAYS),
        },
    )
    # A repeat is a benign, non-disclosing operation. It does not reset
    # expiry or confer enrollment/eligibility. Deletion requires owner approval.
    return created
