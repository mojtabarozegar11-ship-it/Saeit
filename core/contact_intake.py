"""Normalize customer-provided contact email for prelaunch enquiry intake only.

Syntactic validation is NOT ownership verification or permission to send email.
Reserved domains must never inflate genuine-prospect counts in the CRM.
"""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

RESERVED_DOMAINS = frozenset((
    "example.com", "example.org", "example.net", "guest.mojplaywin.com",
))


def canonical_contact_email(value):
    if (type(value) is not str or not value or len(value) > 254
            or value != value.strip()):
        raise ValidationError("Invalid contact email")
    email = value.lower()
    validate_email(email)
    domain = email.rsplit("@", 1)[1]
    if (domain in RESERVED_DOMAINS or domain.endswith(".invalid")
            or domain.endswith(".local") or domain.endswith(".test")
            or domain.endswith(".example")):
        raise ValidationError("Reserved or non-deliverable contact domain")
    return email
