"""Fail-closed REAL MOJ-PROP-01 invoice authorization boundary.

No wallet display, invoice creation, RPC, credit, settlement or payment request.
Only accepts independently attested server-side facts; never browser assertions.
The authoritative order service must persist a signed, versioned enrollment and
perform the actual transaction and cross-product UNIQUE(network,txid) commit.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
import re

PRODUCT = "MOJ-PROP-01"
VERSION = "2026-11-15/v1.2"
NETWORK = "tron-mainnet"
AMOUNT_SUN = 30_000_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ORDER = re.compile(r"MOJPROP01-[A-Z0-9]{12,32}\Z")

class InvoiceBoundaryRejected(ValueError):
    pass

# Each fact must originate from its independently authenticated authoritative service.
REQUIRED_PROOFS = (
    "authenticated_buyer", "buyer_kyc_passed", "buyer_eligible",
    "jurisdiction_legal", "merchant_legal", "product_legal",
    "sanctions_screened", "age_verified", "risk_disclosure_accepted",
    "signed_contract_verified", "bilingual_terms_verified",
    "terms_version_verified", "capital_available_verified",
    "capital_custody_verified", "broker_authorized_verified",
    "broker_operational_verified", "merchant_wallet_control_verified",
    "merchant_wallet_network_verified", "restore_drill_verified",
    "sales_release_approved",
)

@dataclass(frozen=True)
class TrustedFact:
    source: str
    subject: str
    passed: bool
    evidence_sha256: str
    checked_at: int
    valid_until: int

@dataclass(frozen=True)
class Enrollment:
    enrollment_id: str
    buyer_id: str
    product: str
    contract_version: str
    signed_terms_sha256: str
    network: str
    amount_sun: int
    status: str

def authorize_candidate(
    enrollment: Enrollment, facts: Mapping[str, TrustedFact], *,
    expected_terms_sha256: str, now: int, trusted_sources: Mapping[str, str],
) -> dict:
    """Returns non-payable authorization evidence, never a checkout or invoice."""
    if type(enrollment) is not Enrollment or type(now) is not int or now <= 0:
        raise InvoiceBoundaryRejected("invalid server enrollment or clock")
    if not ORDER.fullmatch(enrollment.enrollment_id):
        raise InvoiceBoundaryRejected("invalid canonical enrollment ID")
    if not isinstance(enrollment.buyer_id, str) or not enrollment.buyer_id.strip():
        raise InvoiceBoundaryRejected("missing authenticated buyer")
    if (enrollment.product != PRODUCT or enrollment.contract_version != VERSION
            or enrollment.network != NETWORK or type(enrollment.amount_sun) is not int
            or enrollment.amount_sun != AMOUNT_SUN or enrollment.status != "approved"):
        raise InvoiceBoundaryRejected("not an approved REAL Plan1 enrollment")
    if (type(expected_terms_sha256) is not str
            or not HEX64.fullmatch(expected_terms_sha256)
            or expected_terms_sha256 == "0" * 64
            or enrollment.signed_terms_sha256 != expected_terms_sha256):
        raise InvoiceBoundaryRejected("terms digest must come from independent signed repository")
    if type(facts) is not dict or type(trusted_sources) is not dict:
        raise InvoiceBoundaryRejected("trusted service proof maps required")
    if set(facts) != set(REQUIRED_PROOFS) or set(trusted_sources) != set(REQUIRED_PROOFS):
        raise InvoiceBoundaryRejected("exact 20 independent proofs required")
    for name in REQUIRED_PROOFS:
        fact = facts[name]
        if (type(fact) is not TrustedFact or type(fact.source) is not str
                or fact.source != trusted_sources[name] or not fact.source
                or fact.subject != enrollment.enrollment_id
                or fact.passed is not True
                or type(fact.evidence_sha256) is not str
                or not HEX64.fullmatch(fact.evidence_sha256)
                or fact.evidence_sha256 == "0" * 64
                or type(fact.checked_at) is not int
                or type(fact.valid_until) is not int
                or not fact.checked_at <= now < fact.valid_until):
            raise InvoiceBoundaryRejected("untrusted, expired or failed proof: " + name)
    return {
        "enrollment_id": enrollment.enrollment_id,
        "product": PRODUCT,
        "network": NETWORK,
        "amount_sun": AMOUNT_SUN,
        "contract_version": VERSION,
        "terms_sha256": expected_terms_sha256,
        "proof_digests": {name: facts[name].evidence_sha256 for name in REQUIRED_PROOFS},
        "payable": False,
        "wallet_request": False,
        "credit": False,
        "settled": False,
    }
