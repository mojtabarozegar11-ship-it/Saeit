"""Plan1 B: bind accepted revised buyer-specific terms to previous review.

This is NOT a new contract form or a customer signature service. The
independent contract vault and acceptance provider must establish actual
consent and authenticity before signing their reference packet. The module
only checks source-version, buyer, seller, SHA-256 and independent HMAC
provenance. A document digest alone NEVER proves a lawful customer contract,
KYC, payment, real capital or the ability to open a live broker account.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re

from .buyer_order_review import Plan1OrderGateClosed, REF
from .order_readiness import SKU, TERMS_VERSION
from .plan1_buyer_no_social_amendment import (
    buyer_no_social_post_amendment, current_plan1_buyer_copy,
)
from .plan1_orm_consent_review import VerifiedPrivateHandoff

SCHEMA = "mojprop.plan1.waived-post-demo-buyer-contract-provenance.v1"
PURPOSE = "buyer_specific_terms_and_no_social_demo_clarification_private"
PROOF = re.compile(r"[0-9a-f]{64}\Z")
MIN_EPOCH = 1735689600
MAX_ACCEPTANCE_WINDOW_SEC = 3600
REQUIRED_FIELDS = frozenset((
    "schema", "purpose", "interest_pk", "request_ref", "buyer_ref",
    "seller_ref", "sku", "historical_terms_version", "amendment_version",
    "prior_contract_pdf_sha256", "accepted_buyer_contract_pdf_sha256",
    "buyer_acceptance_proof_sha256", "current_copy_sha256",
    "no_post_waiver_sha256", "fee_native_sun", "network",
    "demo_phase_count", "no_real_account_during_evaluation",
    "live_broker_only_after_both_verified_passes",
    "no_buyer_instagram_or_facebook_post", "posting_is_not_pass_condition",
    "legal_purchase_screening_still_applies", "accepted_at_sec",
    "expires_at_sec",
))


@dataclass(frozen=True)
class RevisedBuyerTermsReview:
    """Opaque provenance only, deliberately not commerce or signed-law proof."""
    interest_pk: int
    request_ref: str
    buyer_ref: str
    seller_ref: str
    sku: str
    prior_contract_digest: str
    revised_buyer_document_digest: str
    waiver_digest: str
    current_disclosure_digest: str
    acceptance_reference_digest: str
    historical_terms_version: str = TERMS_VERSION
    status: str = "PRIVATE_BUYER_TERMS_PROVENANCE_REVIEW_ONLY"
    buyer_signature_legally_verified_by_this_code: bool = False
    independent_purchase_kyc_verified_by_this_code: bool = False
    seller_authority_verified_by_this_code: bool = False
    payer_funding_verified_by_this_code: bool = False
    invoice_created: bool = False
    customer_payment_received: bool = False
    demo_account_created: bool = False
    real_account_created: bool = False
    marketing_consent: bool = False
    buyer_social_posts_required: int = 0


def bind_revised_buyer_terms(
    *, existing_private_handoff, signed_acceptance_packet,
    acceptance_hmac_hex, trusted_acceptance_provider_key,
    trusted_independent_reviewer_key, expected_accepted_pdf_sha256,
    expected_buyer_signature_proof_sha256, server_now_sec,
):
    """Prove cryptographic *lineage* to buyer's new waiver, not legal validity.

    Never construct a receipt/invoice from this output. Trusted proof digests
    must come from access-controlled real acceptance evidence, not user JSON.
    No old 1-post/platform source clause can be passed as current acceptance.
    """
    h = existing_private_handoff
    if (type(h) is not VerifiedPrivateHandoff
            or type(h.interest_pk) is not int or h.interest_pk <= 0
            or type(h.request_ref) is not str or REF.fullmatch(h.request_ref) is None
            or type(h.buyer_ref) is not str or REF.fullmatch(h.buyer_ref) is None
            or type(h.seller_ref) is not str or REF.fullmatch(h.seller_ref) is None
            or h.state != "PRIVATE_SIGNED_EVIDENCE_REVIEW_ONLY"
            or any(getattr(h, field) is not False for field in (
                "contact_authorized", "marketing_authorized",
                "payable_invoice_created", "payment_confirmed",
                "enrollment_created", "funded_account_created",
            ))):
        raise Plan1OrderGateClosed("prior private signed buyer review required")
    for v in (
        h.contract_pdf_sha256, h.inquiry_sha256,
        h.buyer_signature_proof_sha256, h.seller_signature_proof_sha256,
        expected_accepted_pdf_sha256, expected_buyer_signature_proof_sha256,
    ):
        if type(v) is not str or PROOF.fullmatch(v) is None or v == "0"*64:
            raise Plan1OrderGateClosed("independent prior/current contract proof missing")
    if (type(trusted_acceptance_provider_key) is not bytes
            or type(trusted_independent_reviewer_key) is not bytes
            or len(trusted_acceptance_provider_key) < 32
            or len(trusted_independent_reviewer_key) < 32
            or hmac.compare_digest(trusted_acceptance_provider_key,
                                   trusted_independent_reviewer_key)):
        raise Plan1OrderGateClosed("independent legal acceptance and review authorities required")
    if (type(server_now_sec) is not int or server_now_sec < MIN_EPOCH
            or type(h.expires_at_sec) is not int
            or server_now_sec >= h.expires_at_sec):
        raise Plan1OrderGateClosed("trusted clock or prior review expired")
    if (type(signed_acceptance_packet) is not dict
            or set(signed_acceptance_packet) != REQUIRED_FIELDS
            or type(acceptance_hmac_hex) is not str
            or PROOF.fullmatch(acceptance_hmac_hex) is None):
        raise Plan1OrderGateClosed("exact signed buyer-specific accepted terms required")
    copy = current_plan1_buyer_copy()
    waiver = buyer_no_social_post_amendment()
    expected = {
        "schema": SCHEMA, "purpose": PURPOSE,
        "interest_pk": h.interest_pk, "request_ref": h.request_ref,
        "buyer_ref": h.buyer_ref, "seller_ref": h.seller_ref,
        "sku": SKU, "historical_terms_version": TERMS_VERSION,
        "amendment_version": waiver.amendment_version,
        "prior_contract_pdf_sha256": h.contract_pdf_sha256,
        "accepted_buyer_contract_pdf_sha256": expected_accepted_pdf_sha256,
        "buyer_acceptance_proof_sha256": expected_buyer_signature_proof_sha256,
        "current_copy_sha256": copy.digest_sha256,
        "no_post_waiver_sha256": waiver.digest_sha256,
        "fee_native_sun": 30_000_000, "network": "TRON-mainnet",
        "demo_phase_count": 2, "no_real_account_during_evaluation": True,
        "live_broker_only_after_both_verified_passes": True,
        "no_buyer_instagram_or_facebook_post": True,
        "posting_is_not_pass_condition": True,
        "legal_purchase_screening_still_applies": True,
    }
    for field, value in expected.items():
        if (type(signed_acceptance_packet[field]) is not type(value)
                or signed_acceptance_packet[field] != value):
            raise Plan1OrderGateClosed("signed buyer acceptance policy or binding mismatch")
    accepted = signed_acceptance_packet["accepted_at_sec"]
    expiry = signed_acceptance_packet["expires_at_sec"]
    if (type(accepted) is not int or type(expiry) is not int
            or not MIN_EPOCH <= accepted <= server_now_sec < expiry
            or expiry > h.expires_at_sec
            or not 0 < expiry - accepted <= MAX_ACCEPTANCE_WINDOW_SEC):
        raise Plan1OrderGateClosed("expired, early or future acceptance evidence")
    body = json.dumps(signed_acceptance_packet, sort_keys=True,
                      ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")
    if len(body) > 8192:
        raise Plan1OrderGateClosed("oversized signed buyer accepted-terms evidence")
    mac = hmac.new(trusted_acceptance_provider_key, body, sha256).hexdigest()
    if not hmac.compare_digest(mac, acceptance_hmac_hex):
        raise Plan1OrderGateClosed("acceptance provenance signature mismatch")
    return RevisedBuyerTermsReview(
        interest_pk=h.interest_pk, request_ref=h.request_ref,
        buyer_ref=h.buyer_ref, seller_ref=h.seller_ref, sku=SKU,
        prior_contract_digest=h.contract_pdf_sha256,
        revised_buyer_document_digest=expected_accepted_pdf_sha256,
        waiver_digest=waiver.digest_sha256,
        current_disclosure_digest=copy.digest_sha256,
        acceptance_reference_digest=sha256(body).hexdigest(),
    )
