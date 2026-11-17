"""B-only independent review boundary; never authorizes commerce.

This adapter composes existing buyer terms provenance with a separately signed
reviewer attestation. Keys and evidence must come from trusted private adapters.
No customer PII, payment, enrollment, or social account access occurs here.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json

from .buyer_order_review import Plan1OrderGateClosed
from .plan1_revised_buyer_terms_link import bind_revised_buyer_terms
from .plan1_independent_reviewer_attestation import (
    ReviewerAttestationClosed, verify_independent_reviewer,
)


@dataclass(frozen=True)
class IndependentlyReviewedTerms:
    """Private evidence only: all commerce privileges remain false."""
    acceptance_sha256: str
    review_ref: str
    reviewer_attestation_sha256: str
    state: str = "PRIVATE_INDEPENDENT_REVIEW_ONLY"
    identity_verified: bool = False
    legal_signature_verified: bool = False
    jurisdiction_verified: bool = False
    capital_verified: bool = False
    invoice_authorized: bool = False
    payment_authorized: bool = False
    enrollment_authorized: bool = False
    real_account_authorized: bool = False
    marketing_authorized: bool = False


def bind_independently_reviewed_terms(
    *, existing_private_handoff, signed_acceptance_packet,
    acceptance_hmac_hex, trusted_acceptance_provider_key,
    trusted_independent_reviewer_key, expected_accepted_pdf_sha256,
    expected_buyer_signature_proof_sha256, server_now_sec,
    review_ref, reviewer_attestation, reviewer_hmac,
):
    """Reject unsigned reviewer evidence; return a non-commerce review record.

    This does not consume review_ref; an atomic private replay registry is
    mandatory before any future irreversible state transition.
    """
    try:
        prior = bind_revised_buyer_terms(
            existing_private_handoff=existing_private_handoff,
            signed_acceptance_packet=signed_acceptance_packet,
            acceptance_hmac_hex=acceptance_hmac_hex,
            trusted_acceptance_provider_key=trusted_acceptance_provider_key,
            trusted_independent_reviewer_key=trusted_independent_reviewer_key,
            expected_accepted_pdf_sha256=expected_accepted_pdf_sha256,
            expected_buyer_signature_proof_sha256=expected_buyer_signature_proof_sha256,
            server_now_sec=server_now_sec,
        )
        if prior.status != "PRIVATE_BUYER_TERMS_PROVENANCE_REVIEW_ONLY":
            raise Plan1OrderGateClosed("unrecognized buyer terms review state")
        if any((
            prior.invoice_created, prior.customer_payment_received,
            prior.demo_account_created, prior.real_account_created,
            prior.marketing_consent, prior.buyer_signature_legally_verified_by_this_code,
            prior.independent_purchase_kyc_verified_by_this_code,
            prior.seller_authority_verified_by_this_code,
            prior.payer_funding_verified_by_this_code,
        )):
            raise Plan1OrderGateClosed("buyer review unexpectedly grants authority")
        verify_independent_reviewer(
            acceptance_digest=prior.acceptance_reference_digest,
            review_ref=review_ref,
            reviewer_attestation=reviewer_attestation,
            reviewer_hmac=reviewer_hmac,
            reviewer_key=trusted_independent_reviewer_key,
            acceptance_provider_key=trusted_acceptance_provider_key,
            now_sec=server_now_sec,
        )
        raw = json.dumps(reviewer_attestation, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("ascii")
        return IndependentlyReviewedTerms(
            acceptance_sha256=prior.acceptance_reference_digest,
            review_ref=review_ref,
            reviewer_attestation_sha256=sha256(raw).hexdigest(),
        )
    except (ReviewerAttestationClosed, ValueError, TypeError, KeyError,
            UnicodeError, OverflowError) as exc:
        raise Plan1OrderGateClosed("independent buyer review evidence rejected") from None
