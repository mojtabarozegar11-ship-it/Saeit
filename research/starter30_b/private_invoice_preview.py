"""Offline, non-payable Starter30 invoice preview. No database, RPC or email side effects.

The merchant must separately verify lawful seller identity, buyer consent and
contract signatures before issuing a real invoice. This module cannot mark paid.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unicodedata

from services.mojprop_starter30_tron_settlement import (
    PRODUCT as SKU,
    NATIVE_AMOUNT_SUN as AMOUNT_SUN,
    NETWORK,
    MERCHANT_DOMAIN,
    MERCHANT_ID,
    REFERENCE as _ORDER,
)

# The canonical persisted TRON order contract permits MAX 86400 seconds.
# A longer private preview must not later masquerade as a valid live invoice.
MAX_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class PrivateInvoicePreview:
    order_ref: str
    sku: str
    network: str
    merchant_domain: str
    merchant_id: str
    amount_sun: int
    issued_at: str
    expires_at: str
    buyer_reference_digest: str
    consent_evidence_digest: str
    contract_version_digest: str
    buyer_signature_digest: str
    seller_signature_digest: str
    status: str = "draft_non_payable"


def _digest(value: str, field: str) -> str:
    if type(value) is not str or not 1 <= len(value.strip()) <= 2048:
        raise ValueError(f"{field} evidence required")
    # Refuse control characters and bidi formatting that can alter apparent
    # consent/contract text. Neither a digest nor the supplied flags prove
    # the original signature was independently authenticated.
    if any(
        unicodedata.category(char) in ("Cc", "Cf", "Cs", "Zl", "Zp")
        for char in value
    ):
        raise ValueError(f"{field} contains unsafe evidence characters")
    return sha256(value.encode("utf-8")).hexdigest()


def _timestamp(value: datetime, field: str) -> datetime:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None):
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def prepare_private_invoice(
    *, order_ref: str, buyer_reference: str, consent_evidence: str,
    contract_version: str, buyer_signature: str, seller_signature: str,
    issued_at: datetime, expires_at: datetime, verified_merchant: bool = False,
    verified_buyer: bool = False, consent_confirmed: bool = False,
    signatures_verified: bool = False,
) -> PrivateInvoicePreview:
    """Generate a non-payable preview only after documented identity/consent gates.

    The flags must be supplied by an independently audited verification process;
    this function is not itself identity or signature verification.
    """
    if type(order_ref) is not str or not _ORDER.fullmatch(order_ref):
        raise ValueError("invalid unique order reference")
    gates = (verified_merchant, verified_buyer, consent_confirmed, signatures_verified)
    if not all(type(gate) is bool and gate is True for gate in gates):
        raise ValueError("explicit boolean identity, consent and signature evidence required")
    issued = _timestamp(issued_at, "issued_at")
    expires = _timestamp(expires_at, "expires_at")
    if not issued < expires <= issued + MAX_TTL:
        raise ValueError("expiry must be after issue and within 24 hours")
    return PrivateInvoicePreview(
        order_ref=order_ref, sku=SKU, network=NETWORK,
        merchant_domain=MERCHANT_DOMAIN, merchant_id=MERCHANT_ID,
        amount_sun=AMOUNT_SUN,
        issued_at=issued.isoformat(), expires_at=expires.isoformat(),
        buyer_reference_digest=_digest(buyer_reference, "buyer_reference"),
        consent_evidence_digest=_digest(consent_evidence, "consent_evidence"),
        contract_version_digest=_digest(contract_version, "contract_version"),
        buyer_signature_digest=_digest(buyer_signature, "buyer_signature"),
        seller_signature_digest=_digest(seller_signature, "seller_signature"),
    )
