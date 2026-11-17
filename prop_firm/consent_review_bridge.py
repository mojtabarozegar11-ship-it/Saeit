"""Read-only Plan 1 consent-to-legal-review bridge.

Never issues invoices, accepts payment, creates enrollments, migrates PII or
claims an informational disclosure is a customer-signed agreement.
"""
from dataclasses import dataclass, field
from hashlib import sha256
import hmac
import re

from .order_readiness import SKU, TERMS_VERSION, REQUIRED, assess_plan_one

_HEX = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")


class BridgeClosed(ValueError):
    """Unverified provenance or contradictory purchase authority."""


@dataclass(frozen=True)
class ConsentReviewBridge:
    # Private buyer binding, DB row identifier and attested digests must not
    # appear in ordinary log/exception repr(). Internal properties are retained.
    interest_ref: str = field(repr=False)
    interest_digest: str = field(repr=False)
    buyer_ref: str = field(repr=False)
    contract_sha256: str = field(repr=False)
    missing_gates: tuple[str, ...]
    state: str = "private_review_only"
    invoice_authorized: bool = False
    payment_authorized: bool = False
    enrollment_authorized: bool = False
    marketing_authorized: bool = False


def prepare_consent_review(*, interest_ref: str, interest_digest: str,
                           buyer_ref: str, consent_recorded: bool,
                           independent_buyer_link_verified: bool,
                           signed_customer_terms_sha256: str,
                           trusted_contract_sha256: str,
                           trusted_gate_evidence: dict) -> ConsentReviewBridge:
    """Bridge only authenticated, consented PropInterest provenance.

    All parameters must be populated by private authenticated adapters, not
    public request JSON. This function neither authenticates those adapters
    nor verifies a signature, identity, jurisdiction, funds or TRON receipt.
    It intentionally cannot release a payable invoice even if gates pass.
    """
    for value in (interest_ref, buyer_ref):
        if type(value) is not str or _REF.fullmatch(value) is None:
            raise BridgeClosed("invalid private reference")
    if (type(interest_digest) is not str
            or _HEX.fullmatch(interest_digest) is None
            or interest_digest == "0" * 64):
        raise BridgeClosed("missing immutable interest provenance")
    if consent_recorded is not True:
        raise BridgeClosed("interest consent not independently recorded")
    if independent_buyer_link_verified is not True:
        raise BridgeClosed("buyer-to-interest binding not independently verified")
    if (type(signed_customer_terms_sha256) is not str
            or _HEX.fullmatch(signed_customer_terms_sha256) is None
            or type(trusted_contract_sha256) is not str
            or _HEX.fullmatch(trusted_contract_sha256) is None
            or signed_customer_terms_sha256 == "0" * 64
            or trusted_contract_sha256 == "0" * 64
            or hmac.compare_digest(interest_digest, trusted_contract_sha256)
            or not hmac.compare_digest(signed_customer_terms_sha256,
                                       trusted_contract_sha256)):
        raise BridgeClosed("independently signed customer terms not bound")
    if type(trusted_gate_evidence) is not dict:
        raise BridgeClosed("missing trusted gate evidence")
    # The existing 20-gate engine is the sole authority for readiness checks.
    # No buyer-supplied claim is promoted to a trusted gate by this bridge.
    readiness = assess_plan_one(trusted_gate_evidence, sku=SKU,
                                contract_version=TERMS_VERSION)
    if readiness.eligible and len(REQUIRED) != 20:
        raise BridgeClosed("unexpected canonical gate schema")
    return ConsentReviewBridge(
        interest_ref=interest_ref,
        interest_digest=interest_digest,
        buyer_ref=buyer_ref,
        contract_sha256=trusted_contract_sha256,
        missing_gates=readiness.missing,
    )
