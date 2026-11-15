"""One subscriber entitlement across all Mojtaba.bot.ai signal brand mirrors.

This is a pure authenticated access decision, NOT a TRX receipt verifier, paid
subscription issuer, brokerage adapter, marketing or user messaging service.
Only separately trusted gateway/reconciliation configuration may issue leases;
an HMAC alone does not prove blockchain finality or legal permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re

from .signal_commercial_catalog import CANONICAL_AGENT, SIGNAL_BRANDS
from .signal_product_plans import SIGNAL_PLANS

SKU_BY_NAME = {p.sku: p for p in SIGNAL_PLANS}
INVOICE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,95}\Z")
TENANT = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,79}\Z")
EMAIL_SIMPLE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\Z")
MAX_TERM_DAYS = 366


class SignalEntitlementError(ValueError):
    pass


def canonical_buyer_email(raw):
    """Bounded non-placeholder ASCII email for case-insensitive buyer matching.

    Mailbox existence, ownership and deliverability must be verified separately.
    A syntactically plausible email is never proof of entitlement by itself.
    """
    if type(raw) is not str or len(raw) > 254 or not raw.isascii():
        raise SignalEntitlementError("buyer_email_invalid")
    value = raw.strip().lower()
    if value != raw.lower() or not EMAIL_SIMPLE.fullmatch(value):
        raise SignalEntitlementError("buyer_email_invalid")
    local, domain = value.rsplit("@", 1)
    if (not local or len(local) > 64 or local.startswith(".")
            or local.endswith(".") or ".." in local
            or domain.startswith(".") or domain.endswith(".")
            or ".." in domain or "." not in domain
            or any(not label or len(label) > 63 or label.startswith("-")
                   or label.endswith("-") for label in domain.split("."))
            or domain in ("example.com", "example.org", "example.net",
                          "guest.mojplaywin.com")
            or domain.endswith(".invalid") or domain.endswith(".local")):
        raise SignalEntitlementError("buyer_email_invalid")
    return value


def _utc(value, field):
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise SignalEntitlementError(field + "_not_utc")
    return value


def _key(key):
    if type(key) is not bytes or len(key) < 32:
        raise SignalEntitlementError("entitlement_signing_key_missing")
    return key


@dataclass(frozen=True)
class SignedSignalLease:
    """Hashed email and invoice only; never return the buyer's raw email."""

    sku: str
    buyer_digest: str
    merchant_tenant_id: str
    invoice_id: str
    issued_at_utc: str
    expires_at_utc: str
    issuing_bot: str
    hmac_sha256: str


def _buyer_digest(email, key):
    """Keyed email pseudonym: public SHA256(address) is dictionary-reversible."""
    return hmac.new(key, b"moj.signal.buyer.v2\x00" + email.encode("ascii"), sha256).hexdigest()


def _claim_payload(lease):
    data = {
        "format": "moj.signal.single_global_entitlement.v2",
        "sku": lease.sku,
        "buyer_digest": lease.buyer_digest,
        "merchant_tenant_id": lease.merchant_tenant_id,
        "invoice_id": lease.invoice_id,
        "issued_at_utc": lease.issued_at_utc,
        "expires_at_utc": lease.expires_at_utc,
        "issuing_bot": lease.issuing_bot,
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("ascii")


def _verify_shape(lease, now_utc):
    if not isinstance(lease, SignedSignalLease):
        return False
    if (type(lease.sku) is not str or lease.sku not in SKU_BY_NAME
            or type(lease.issuing_bot) is not str
            or lease.issuing_bot != CANONICAL_AGENT
            or type(lease.invoice_id) is not str
            or INVOICE.fullmatch(lease.invoice_id) is None
            or type(lease.merchant_tenant_id) is not str
            or TENANT.fullmatch(lease.merchant_tenant_id) is None
            or type(lease.buyer_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", lease.buyer_digest) is None
            or type(lease.hmac_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", lease.hmac_sha256) is None):
        return False
    try:
        issued = datetime.fromisoformat(lease.issued_at_utc)
        expires = datetime.fromisoformat(lease.expires_at_utc)
        _utc(issued, "lease_start")
        _utc(expires, "lease_end")
    except (TypeError, ValueError, SignalEntitlementError):
        return False
    return bool(issued <= now_utc < expires
                and timedelta(0) < expires - issued <= timedelta(days=MAX_TERM_DAYS))


def issue_signal_lease(*, trusted_gateway_invoice, verified_buyer_email,
                       merchant_tenant_id, sku, issued_at_utc, expires_at_utc,
                       signing_key):
    """Trusted gateway adapter only; no external payment or email I/O.

    An invoice string is not proof of payment. The adapter MUST call this only
    after independent on-chain finality and an internal durable entitlement
    write, and must never expose signing_key to website clients.
    """
    _key(signing_key)
    email = canonical_buyer_email(verified_buyer_email)
    _utc(issued_at_utc, "issued")
    _utc(expires_at_utc, "expires")
    if (type(sku) is not str or sku not in SKU_BY_NAME
            or type(trusted_gateway_invoice) is not str
            or INVOICE.fullmatch(trusted_gateway_invoice) is None
            or type(merchant_tenant_id) is not str
            or TENANT.fullmatch(merchant_tenant_id) is None
            or not issued_at_utc < expires_at_utc
            or expires_at_utc - issued_at_utc > timedelta(days=MAX_TERM_DAYS)):
        raise SignalEntitlementError("lease_contract_invalid")
    lease = SignedSignalLease(
        sku=sku,
        buyer_digest=_buyer_digest(email, signing_key),
        merchant_tenant_id=merchant_tenant_id,
        invoice_id=trusted_gateway_invoice,
        issued_at_utc=issued_at_utc.isoformat(),
        expires_at_utc=expires_at_utc.isoformat(),
        issuing_bot=CANONICAL_AGENT,
        hmac_sha256="",
    )
    digest = hmac.new(signing_key, _claim_payload(lease), sha256).hexdigest()
    return SignedSignalLease(**{**lease.__dict__, "hmac_sha256": digest})


def verify_signal_access(*, lease, buyer_email, requested_sku, mirror_brand,
                         now_utc, signing_key, independently_reconciled_invoices,
                         revoked_invoice_ids=()):
    """One SKU is recognized by all mirrors; never charges or renews an invoice.

    The reconciled-invoice set must come from an independently audited,
    server-only gateway ledger, not a request body. A valid source HMAC
    without that independent record NEVER authorizes content access.
    """
    if type(mirror_brand) is not str or mirror_brand not in SIGNAL_BRANDS:
        return False
    if type(requested_sku) is not str or requested_sku not in SKU_BY_NAME:
        return False
    if (not isinstance(independently_reconciled_invoices, (frozenset, set))
            or not isinstance(revoked_invoice_ids, (frozenset, set, tuple))):
        return False
    try:
        _utc(now_utc, "observation")
        _key(signing_key)
        email = canonical_buyer_email(buyer_email)
    except SignalEntitlementError:
        return False
    if (not _verify_shape(lease, now_utc)
            or lease.sku != requested_sku
            or lease.invoice_id not in independently_reconciled_invoices
            or lease.invoice_id in revoked_invoice_ids
            or not hmac.compare_digest(lease.buyer_digest,
                                       _buyer_digest(email, signing_key))):
        return False
    expected = hmac.new(signing_key, _claim_payload(lease), sha256).hexdigest()
    return hmac.compare_digest(expected, lease.hmac_sha256)


def authorized_signal_delivery_preflight(
        *, lease, buyer_email, requested_sku, mirror_brand, now_utc,
        signing_key, independently_reconciled_invoices, revoked_invoice_ids,
        signal_record, source_id, source_signature, trusted_source_keys,
        durable_seen_event_ids, jurisdiction_and_delivery_rights_verified):
    """Return an authorized *delivery decision* only, never message/charge.

    Both independent buyer entitlement and source provenance must pass.
    Caller must load ledger, source keys and jurisdiction evidence from its
    own protected backend; never forward an untrusted request body as proof.
    A successful decision is for ONE individually authenticated delivery and
    does not renew an invoice, publish a site or create a profitable trade.
    """
    if jurisdiction_and_delivery_rights_verified is not True:
        return {"eligible_to_deliver": False, "reason": "jurisdiction_or_delivery_rights"}
    if not verify_signal_access(
            lease=lease, buyer_email=buyer_email,
            requested_sku=requested_sku, mirror_brand=mirror_brand,
            now_utc=now_utc, signing_key=signing_key,
            independently_reconciled_invoices=independently_reconciled_invoices,
            revoked_invoice_ids=revoked_invoice_ids):
        return {"eligible_to_deliver": False, "reason": "unpaid_or_invalid_entitlement"}
    from .signal_source_evidence import authenticate_signal_source
    verified = authenticate_signal_source(
        record=signal_record, brand=mirror_brand, source_id=source_id,
        signature=source_signature, trusted_source_keys=trusted_source_keys,
        seen_event_ids=durable_seen_event_ids, now=now_utc)
    if verified.source_authenticated is not True:
        return {"eligible_to_deliver": False, "reason": "untrusted_signal_source"}
    return {
        "eligible_to_deliver": True,
        "source_evidence_sha256": verified.audit_digest_sha256,
        "canonical_bot": CANONICAL_AGENT,
        "entitlement_sku": lease.sku,
        "signal_event_id": signal_record["event_id"],
        "delivery_performed": False,
        "performance_verified": False,
        "payment_processed": False,
    }
