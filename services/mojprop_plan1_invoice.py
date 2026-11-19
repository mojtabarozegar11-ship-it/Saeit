"""Trusted Plan 1 invoice contract for the real MOJ-PROP-01 offer.

This module is deliberately an invoice *contract*, not a checkout endpoint.
It refuses to issue a payable snapshot until every independent release gate is
true. It never calls a network, writes a database, sends mail, or grants a
funded account. The effective cPanel gateway must persist this exact snapshot
and use a global unique settlement ledger before any entitlement is granted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Mapping

PRODUCT = "MOJ-PROP-01"
CONTRACT_VERSION = "2026-11-15/v1.2"
NETWORK = "tron-mainnet"
ASSET = "TRX"
AMOUNT_SUN = 30_000_000
MERCHANT_DOMAIN = "mojplaywin.com"
MERCHANT_ID = "mojplaywin-store"
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ORDER_REF = re.compile(r"MOJPROP01-[A-Z0-9]{12,32}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

RELEASE_GATES = (
    "merchant_identity_approved",
    "jurisdiction_approved",
    "treasury_capital_independently_verified",
    "broker_contract_compatibility_verified",
    "identity_screening_ready",
    "customer_terms_approved",
    "refund_and_dispute_process_ready",
    "tron_settlement_reconciler_verified",
    "effective_route_registered",
)


class InvoiceReleaseDenied(ValueError):
    """The real Plan 1 invoice cannot be issued yet."""


@dataclass(frozen=True)
class ReleaseDecision:
    invoice_enabled: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class Plan1InvoiceSnapshot:
    product: str
    order_ref: str
    email: str
    merchant_domain: str
    merchant_id: str
    network: str
    asset: str
    recipient: str
    amount_sun: int
    issued_at: datetime
    expires_at: datetime
    buyer_terms_acceptance: str
    contract_version: str
    contract_sha256: str
    payer_hex41: str | None = None


def _strict_true(values: Mapping[str, object], key: str) -> bool:
    return values.get(key) is True


def _decode_tron(address: str) -> bytes:
    if type(address) is not str or not address.startswith("T"):
        raise InvoiceReleaseDenied("invalid TRON recipient")
    value = 0
    try:
        for char in address:
            value = value * 58 + BASE58.index(char)
    except (ValueError, TypeError) as exc:
        raise InvoiceReleaseDenied("invalid TRON recipient") from exc
    raw = value.to_bytes(25, "big")
    if raw[0] != 0x41 or sha256(sha256(raw[:21]).digest()).digest()[:4] != raw[21:]:
        raise InvoiceReleaseDenied("invalid TRON recipient checksum")
    return raw[:21]


def validate_tron_recipient(address: str) -> str:
    raw = _decode_tron(address)
    if len(raw) != 21:
        raise InvoiceReleaseDenied("invalid TRON recipient length")
    return address


def assess_release(*, attestations: Mapping[str, object],
                   owner_declared_active: object,
                   independent_capital_proof: object,
                   protected_recipient: str | None,
                   route_registered: object) -> ReleaseDecision:
    if not isinstance(attestations, Mapping):
        raise InvoiceReleaseDenied("release attestations must be a mapping")
    blockers = [key for key in RELEASE_GATES if not _strict_true(attestations, key)]
    if owner_declared_active is not True:
        blockers.append("owner_plan1_active_declaration_missing")
    if independent_capital_proof is not True:
        blockers.append("independent_plan1_capital_proof_missing")
    if route_registered is not True:
        blockers.append("effective_moj_prop_route_not_registered")
    if type(protected_recipient) is not str:
        blockers.append("protected_tron_recipient_missing")
    else:
        try:
            validate_tron_recipient(protected_recipient)
        except InvoiceReleaseDenied:
            blockers.append("protected_tron_recipient_invalid")
    return ReleaseDecision(invoice_enabled=not blockers, blockers=tuple(blockers))


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InvoiceReleaseDenied(name + " must be timezone-aware")
    return value.astimezone(timezone.utc)


def issue_plan1_invoice(*, decision: ReleaseDecision, email: str,
                        order_ref: str, recipient: str, issued_at: datetime,
                        expires_at: datetime, buyer_terms_acceptance: str,
                        contract_sha256: str, payer_hex41: str | None = None
                        ) -> Plan1InvoiceSnapshot:
    if not isinstance(decision, ReleaseDecision) or decision.invoice_enabled is not True:
        raise InvoiceReleaseDenied("Plan 1 invoice release is not enabled")
    if type(email) is not str or len(email) > 254 or not EMAIL.fullmatch(email.strip().lower()):
        raise InvoiceReleaseDenied("valid buyer email required")
    if type(order_ref) is not str or ORDER_REF.fullmatch(order_ref) is None:
        raise InvoiceReleaseDenied("immutable Plan 1 order reference required")
    validate_tron_recipient(recipient)
    start, end = _aware(issued_at, "issued_at"), _aware(expires_at, "expires_at")
    if not 0 < (end - start).total_seconds() <= 86_400:
        raise InvoiceReleaseDenied("invoice lifetime must be within 24 hours")
    if type(buyer_terms_acceptance) is not str or len(buyer_terms_acceptance) < 8:
        raise InvoiceReleaseDenied("buyer terms acceptance evidence required")
    if type(contract_sha256) is not str or DIGEST.fullmatch(contract_sha256) is None:
        raise InvoiceReleaseDenied("trusted bilingual contract digest required")
    if payer_hex41 is not None and (
        type(payer_hex41) is not str or not re.fullmatch(r"41[0-9a-f]{40}\Z", payer_hex41)
    ):
        raise InvoiceReleaseDenied("invalid pre-bound payer")
    return Plan1InvoiceSnapshot(
        product=PRODUCT, order_ref=order_ref, email=email.strip().lower(),
        merchant_domain=MERCHANT_DOMAIN, merchant_id=MERCHANT_ID,
        network=NETWORK, asset=ASSET, recipient=recipient,
        amount_sun=AMOUNT_SUN, issued_at=start, expires_at=end,
        buyer_terms_acceptance=buyer_terms_acceptance,
        contract_version=CONTRACT_VERSION, contract_sha256=contract_sha256,
        payer_hex41=payer_hex41,
    )
