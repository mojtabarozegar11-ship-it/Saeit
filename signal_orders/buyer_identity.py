"""Guest email canonicalization and tenant-bound private buyer HMAC.

A valid syntax is NOT mailbox-ownership verification. A future email
challenge/receipt process must verify deliverability and ownership separately.
"""
from __future__ import annotations

import hashlib
import hmac
import re


class SignalBuyerIdentityError(ValueError):
    pass


_LOCAL = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")
_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_TENANT = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_DISALLOWED_SUFFIXES = (".invalid", ".test", ".example", ".localhost", ".local")
_DISALLOWED_DOMAINS = frozenset({
    "example.com", "example.net", "example.org", "guest.mojplaywin.com",
})


def canonical_buyer_email(value):
    if (type(value) is not str or not 5 <= len(value) <= 254
            or not value.isascii() or value != value.strip()
            or value.count("@") != 1):
        raise SignalBuyerIdentityError("valid_buyer_email_required")
    local, domain = value.rsplit("@", 1)
    domain = domain.lower()
    if (not 1 <= len(local) <= 64 or not _LOCAL.fullmatch(local)
            or local.startswith(".") or local.endswith(".") or ".." in local
            or len(domain) < 4 or len(domain) > 253
            or domain in _DISALLOWED_DOMAINS
            or domain.endswith(_DISALLOWED_SUFFIXES)
            or domain.startswith(".") or domain.endswith(".")):
        raise SignalBuyerIdentityError("valid_buyer_email_required")
    parts = domain.split(".")
    if (len(parts) < 2 or len(parts[-1]) < 2
            or not parts[-1].isalpha()
            or not all(_LABEL.fullmatch(part) for part in parts)):
        raise SignalBuyerIdentityError("valid_buyer_email_required")
    # Preserve the case-sensitive local part; normalize DNS domain only.
    return local + "@" + domain


def buyer_ref_digest(*, buyer_email, tenant_id, secret):
    canonical = canonical_buyer_email(buyer_email)
    if type(tenant_id) is not str or not _TENANT.fullmatch(tenant_id):
        raise SignalBuyerIdentityError("tenant_identity_invalid")
    if type(secret) is not bytes or len(secret) < 32:
        raise SignalBuyerIdentityError("protected_buyer_secret_required")
    msg = b"mojtaba.signal.guest.v1\x00" + tenant_id.encode("ascii") + b"\x00" + canonical.encode("ascii")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_buyer_ref_digest(*, provided_digest, buyer_email, tenant_id, secret):
    if (type(provided_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", provided_digest) is None):
        return False
    try:
        known = buyer_ref_digest(buyer_email=buyer_email, tenant_id=tenant_id, secret=secret)
    except SignalBuyerIdentityError:
        return False
    return hmac.compare_digest(provided_digest, known)
