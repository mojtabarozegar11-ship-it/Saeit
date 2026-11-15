"""MojPlayWin guest purchase email-to-invoice identity, source-only.

This isolates recovery/receipt ownership from anonymous session cookies.
It does not send emails, create accounts, activate invoices, or bypass the
private checkout's independent TRX finality and order/fulfilment controls.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import hmac
import re

EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\Z")
INVOICE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{7,95}\Z")
MAX_AGE = timedelta(days=30)


class GuestBuyerIdentityError(ValueError):
    pass


def valid_guest_email(value):
    """Validate an actual buyer-supplied address; never accept guest placeholders."""
    if type(value) is not str or not 3 <= len(value) <= 254 or not value.isascii():
        raise GuestBuyerIdentityError("buyer_email_missing_or_invalid")
    email = value.strip().lower()
    if email != value.lower() or EMAIL.fullmatch(email) is None:
        raise GuestBuyerIdentityError("buyer_email_missing_or_invalid")
    local, domain = email.rsplit("@", 1)
    labels = domain.split(".")
    if (len(local) > 64 or local[0] == "." or local.endswith(".")
            or ".." in local or len(labels) < 2
            or not all(label and len(label) <= 63
                       and label[0] != "-" and label[-1] != "-"
                       for label in labels)
            or domain in ("guest.mojplaywin.com", "example.com", "example.org")
            or domain.endswith(".invalid") or domain.endswith(".local")):
        raise GuestBuyerIdentityError("buyer_email_missing_or_invalid")
    return email


def _utc(value):
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise GuestBuyerIdentityError("invalid_server_clock")
    return value


@dataclass(frozen=True)
class GuestInvoiceIdentity:
    invoice_id: str
    principal_id: int
    product_id: int
    buyer_email_digest: str
    bound_at_utc: str
    expires_at_utc: str
    hmac_sha256: str


def _email_digest(canonical_email, signing_key):
    """Keyed pseudonym: unlike plain SHA256, email guessing needs a private key."""
    return hmac.new(signing_key, b"mpw.guest.buyer.v2\\x00" + canonical_email.encode("ascii"), sha256).hexdigest()


def _message(item):
    return "|".join((
        "mojplaywin.guest.invoice.identity.v2",
        item.invoice_id, str(item.principal_id), str(item.product_id),
        item.buyer_email_digest, item.bound_at_utc, item.expires_at_utc,
    )).encode("ascii")


def issue_guest_order_identity(*, buyer_email, invoice_id, principal_id,
                               product_id, bound_at_utc, signing_key):
    """Call only after validated guest email and an authoritative DB invoice."""
    canonical = valid_guest_email(buyer_email)
    if (type(invoice_id) is not str or INVOICE.fullmatch(invoice_id) is None
            or type(principal_id) is not int or principal_id <= 0
            or type(product_id) is not int or product_id <= 0
            or type(signing_key) is not bytes or len(signing_key) < 32):
        raise GuestBuyerIdentityError("guest_invoice_identity_invalid")
    _utc(bound_at_utc)
    expiry = bound_at_utc + MAX_AGE
    item = GuestInvoiceIdentity(
        invoice_id, principal_id, product_id,
        _email_digest(canonical, signing_key),
        bound_at_utc.isoformat(), expiry.isoformat(), "",
    )
    return GuestInvoiceIdentity(**{
        **item.__dict__,
        "hmac_sha256": hmac.new(signing_key, _message(item), sha256).hexdigest(),
    })


def verify_guest_order_identity(*, proof, buyer_email, invoice_id, principal_id,
                                product_id, now_utc, signing_key):
    """Recover only the original invoice and principal, not other guest orders."""
    if not isinstance(proof, GuestInvoiceIdentity):
        return False
    try:
        email = valid_guest_email(buyer_email)
        _utc(now_utc)
        if (type(signing_key) is not bytes or len(signing_key) < 32
                or type(invoice_id) is not str or INVOICE.fullmatch(invoice_id) is None
                or type(principal_id) is not int or principal_id <= 0
                or type(product_id) is not int or product_id <= 0
                or type(proof.hmac_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", proof.hmac_sha256) is None
                or type(proof.buyer_email_digest) is not str
                or re.fullmatch(r"[0-9a-f]{64}", proof.buyer_email_digest) is None):
            return False
        start = datetime.fromisoformat(proof.bound_at_utc)
        end = datetime.fromisoformat(proof.expires_at_utc)
        _utc(start)
        _utc(end)
        if (not start <= now_utc < end or end - start != MAX_AGE
                or (invoice_id, principal_id, product_id)
                != (proof.invoice_id, proof.principal_id, proof.product_id)
                or not hmac.compare_digest(
                    proof.buyer_email_digest, _email_digest(email, signing_key)
                )):
            return False
        return hmac.compare_digest(
            hmac.new(signing_key, _message(proof), sha256).hexdigest(),
            proof.hmac_sha256,
        )
    except (TypeError, ValueError, GuestBuyerIdentityError):
        return False
