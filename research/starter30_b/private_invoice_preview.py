"""Offline, non-payable Starter30 invoice preview. No database, RPC or email side effects.

The merchant must separately verify lawful seller identity, buyer consent and
contract signatures before issuing a real invoice. This module cannot mark paid.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re

SKU = "MOJPROP-STARTER30"
AMOUNT_SUN = 30_000_000
NETWORK = "tron-mainnet"
MAX_TTL = timedelta(days=7)
_HEX = re.compile(r"^[0-9a-f]{64}$")
_ORDER = re.compile(r"^[A-Z0-9][A-Z0-9_-]{7,41}$")


@dataclass(frozen=True)
class PrivateInvoicePreview:
    order_ref: str
    sku: str
    network: str
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
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} evidence required")
    return sha256(value.encode("utf-8")).hexdigest()


def _timestamp(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
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
    if not isinstance(order_ref, str) or not _ORDER.fullmatch(order_ref):
        raise ValueError("invalid unique order reference")
    if not all((verified_merchant, verified_buyer, consent_confirmed, signatures_verified)):
        raise ValueError("independent identity, consent and signature verification required")
    issued = _timestamp(issued_at, "issued_at")
    expires = _timestamp(expires_at, "expires_at")
    if not issued < expires <= issued + MAX_TTL:
        raise ValueError("expiry must be after issue and within seven days")
    return PrivateInvoicePreview(
        order_ref=order_ref, sku=SKU, network=NETWORK, amount_sun=AMOUNT_SUN,
        issued_at=issued.isoformat(), expires_at=expires.isoformat(),
        buyer_reference_digest=_digest(buyer_reference, "buyer_reference"),
        consent_evidence_digest=_digest(consent_evidence, "consent_evidence"),
        contract_version_digest=_digest(contract_version, "contract_version"),
        buyer_signature_digest=_digest(buyer_signature, "buyer_signature"),
        seller_signature_digest=_digest(seller_signature, "seller_signature"),
    )
