"""Cycle B: authenticated ORM-to-private-review adapter; strictly no commerce.

Only an already authenticated staff service may invoke this function. It reads
the current canonical PropInterest row; it does not create a second lead,
alter consent, persist PII, issue an invoice or authorize contact.
"""
from __future__ import annotations

from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone

from .lead_models import PropInterest
from .plan1_canonical_interest_bridge import (
    bind_canonical_interest_to_private_inquiry,
    match_private_review_to_canonical_interest,
)
from .buyer_order_review import Plan1OrderGateClosed
from .plan1_demo_email_interest import review_existing_demo_interest_otp
from .plan1_private_order_draft import (
    _DOCUMENT_BINDINGS,
    build_plan1_private_review_draft,
)


def _require_authorized_staff(actor):
    """Match the owner-private CRM admin boundary: active superuser + permission."""
    if (actor is None or getattr(actor, "is_authenticated", None) is not True
            or getattr(actor, "is_active", None) is not True
            or getattr(actor, "is_staff", None) is not True
            or getattr(actor, "is_superuser", None) is not True):
        raise Plan1OrderGateClosed("authenticated active staff required")
    permission = getattr(actor, "has_perm", None)
    if not callable(permission):
        raise Plan1OrderGateClosed("explicit PropInterest review permission required")
    try:
        authorized = permission("prop_firm.view_propinterest")
    except Exception as exc:
        raise Plan1OrderGateClosed("permission service unavailable") from exc
    if authorized is not True:
        raise Plan1OrderGateClosed("PropInterest review permission denied")


@dataclass(frozen=True)
class VerifiedPrivateHandoff:
    """Bound proof references only; neither executed terms nor a purchase."""
    interest_pk: int
    request_ref: str
    private_review_ref: str
    inquiry_sha256: str
    contract_pdf_sha256: str
    refund_disclosure_sha256: str
    buyer_signature_proof_sha256: str
    seller_signature_proof_sha256: str
    expires_at_sec: int
    state: str = "PRIVATE_SIGNED_EVIDENCE_REVIEW_ONLY"
    contact_authorized: bool = False
    marketing_authorized: bool = False
    executed_contract_independently_proven_by_this_code: bool = False
    kyc_independently_proven_by_this_code: bool = False
    seller_license_independently_proven_by_this_code: bool = False
    capital_available_independently_proven_by_this_code: bool = False
    payable_invoice_created: bool = False
    payment_confirmed: bool = False
    enrollment_created: bool = False
    funded_account_created: bool = False


def review_signed_existing_consent(*, actor, interest_pk, inquiry,
                                   consent_attestation, consent_tag_hex,
                                   consent_key, request_ref, inquiry_sha256,
                                   consent_evidence_sha256):
    """Read-only existing opt-in + independent consent provenance only.

    This is the lightweight pre-KYC DEMO interest boundary; it does NOT
    require a signed buyer purchase contract or the twenty purchase gates.
    The shared PropInterest row must be NEW and not withdrawn or contacted.
    No customer contact, email send, payment, or marketing permission follows.
    """
    _require_authorized_staff(actor)
    if type(interest_pk) is not int or interest_pk <= 0:
        raise Plan1OrderGateClosed("invalid canonical consent record identifier")
    with transaction.atomic():
        row = (PropInterest.objects.select_for_update()
               .filter(pk=interest_pk).values(
                   "id", "email", "plan_code", "consent_version",
                   "source_language", "status").first())
        if row is None:
            raise Plan1OrderGateClosed("canonical consent record unavailable")
        return bind_canonical_interest_to_private_inquiry(
            canonical_interest=row, inquiry=inquiry,
            trusted_consent_attestation=consent_attestation,
            signed_consent_tag_hex=consent_tag_hex,
            trusted_consent_key=consent_key,
            expected_request_ref=request_ref,
            expected_interest_pk=interest_pk,
            expected_inquiry_sha256=inquiry_sha256,
            expected_consent_evidence_sha256=consent_evidence_sha256,
        )


def review_existing_interest(*, actor, interest_pk, inquiry, consent_attestation,
                             consent_tag_hex, consent_key, request_ref,
                             inquiry_sha256, consent_evidence_sha256,
                             private_order_draft):
    """Purchase-case PRIVATE reviewer: requires both consent and signed draft.

    Do not reuse the stricter purchase-review path for light email-only
    interest registration. This method cannot issue an invoice.
    """
    _require_authorized_staff(actor)
    if type(interest_pk) is not int or interest_pk <= 0:
        raise Plan1OrderGateClosed("invalid canonical interest identifier")
    with transaction.atomic():
        link = review_signed_existing_consent(
            actor=actor, interest_pk=interest_pk, inquiry=inquiry,
            consent_attestation=consent_attestation,
            consent_tag_hex=consent_tag_hex, consent_key=consent_key,
            request_ref=request_ref, inquiry_sha256=inquiry_sha256,
            consent_evidence_sha256=consent_evidence_sha256,
        )
        return match_private_review_to_canonical_interest(
            consent_link=link, private_order_draft=private_order_draft)



def review_verified_precontract_for_interest(
    *, actor, interest_pk, inquiry, consent_attestation, consent_tag_hex,
    consent_key, request_ref, inquiry_sha256, consent_evidence_sha256,
    reviewed_packet, reviewer_tag_hex, trusted_reviewer_key,
    intake_tag_hex, trusted_intake_key, expected_buyer_ref,
    expected_seller_ref, trusted_documents,
):
    """Join canonical opt-in to a freshly authenticated PRIVATE buyer review.

    Existing contract review/HMAC producers are reused; no second form,
    contract, KYC store, payable invoice, payment or enrollment is created.
    Caller MUST resolve every trusted input from separate, access-controlled
    server components. Hashes or all-true flags are NOT legal/KYC proof.
    """
    _require_authorized_staff(actor)
    if type(interest_pk) is not int or interest_pk <= 0:
        raise Plan1OrderGateClosed("invalid canonical interest identifier")
    keys = (consent_key, trusted_intake_key, trusted_reviewer_key)
    if any(type(key) is not bytes or len(key) < 32 for key in keys):
        raise Plan1OrderGateClosed("three independent trusted key sources required")
    if len(set(keys)) != 3:
        raise Plan1OrderGateClosed("consent, intake and legal-review roles must differ")
    if (type(trusted_documents) is not dict
            or set(trusted_documents) != set(_DOCUMENT_BINDINGS.values())):
        raise Plan1OrderGateClosed("exact independent document references required")
    now = timezone.now()
    if now.tzinfo is None or now.utcoffset() is None:
        raise Plan1OrderGateClosed("timezone-aware server clock required")
    now_sec = int(now.timestamp())
    if now_sec < 1_735_689_600:
        raise Plan1OrderGateClosed("trusted server clock unavailable")
    # Do not accept a caller-invented clock, review draft, customer signature,
    # wallet receipt or submitted payment status as an authority.
    draft = build_plan1_private_review_draft(
        inquiry=inquiry, reviewed_packet=reviewed_packet,
        reviewer_tag_hex=reviewer_tag_hex,
        trusted_reviewer_key=trusted_reviewer_key,
        intake_tag_hex=intake_tag_hex, trusted_intake_key=trusted_intake_key,
        expected_request_ref=request_ref,
        expected_buyer_ref=expected_buyer_ref,
        expected_seller_ref=expected_seller_ref,
        server_now_sec=now_sec, **trusted_documents,
    )
    if draft.expires_at_sec <= now_sec:
        raise Plan1OrderGateClosed("private signed review has expired")
    link = review_existing_interest(
        actor=actor, interest_pk=interest_pk, inquiry=inquiry,
        consent_attestation=consent_attestation,
        consent_tag_hex=consent_tag_hex, consent_key=consent_key,
        request_ref=request_ref, inquiry_sha256=inquiry_sha256,
        consent_evidence_sha256=consent_evidence_sha256,
        private_order_draft=draft,
    )
    if (link.canonical_interest_pk != interest_pk
            or link.request_ref != draft.original_request_ref
            or link.inquiry_sha256 != draft.inquiry_sha256
            or link.state != "CONSENT_LINK_PRIVATE_REVIEW_ONLY"
            or link.payable is not False
            or link.enrollment_created is not False
            or link.kyc_proven is not False
            or link.buyer_contact_authorized_by_this_module is not False):
        raise Plan1OrderGateClosed("private lineage may not authorize commerce")
    # An expired case must not survive a slow lock acquisition or verification.
    final_now = timezone.now()
    if (final_now.tzinfo is None or final_now.utcoffset() is None
            or draft.expires_at_sec <= int(final_now.timestamp())):
        raise Plan1OrderGateClosed("private review expired during canonical lookup")
    return VerifiedPrivateHandoff(
        interest_pk=interest_pk, request_ref=request_ref,
        private_review_ref=draft.private_review_ref,
        inquiry_sha256=draft.inquiry_sha256,
        contract_pdf_sha256=draft.contract_pdf_sha256,
        refund_disclosure_sha256=draft.refund_disclosure_sha256,
        buyer_signature_proof_sha256=draft.buyer_signature_proof_sha256,
        seller_signature_proof_sha256=draft.seller_signature_proof_sha256,
        expires_at_sec=draft.expires_at_sec,
    )


def review_email_verified_existing_interest(
    *, actor, interest_pk, inquiry, consent_attestation, consent_tag_hex,
    consent_key, request_ref, inquiry_sha256, consent_evidence_sha256,
    signed_otp_receipt, signed_otp_tag_hex,
    trusted_otp_service_key, declared_country, age_18_self_attested,
):
    """Verify OTP for an existing consented CRM prospect, never for payment.

    Server-side staff service is responsible for keeping the OTP signing key
    independent from the consent registry. An email code is validated in the
    separate OTP service, not fabricated from a self-declared browser flag.
    The outer transaction retains the canonical row lock throughout both
    consent and OTP lineage checks to avoid withdrawal race during review.

    This method does NOT send OTP messages, perform real identity KYC, accept
    buyer agreements, activate DEMO/REAL accounts or create payable invoices.
    """
    _require_authorized_staff(actor)
    if type(interest_pk) is not int or interest_pk <= 0:
        raise Plan1OrderGateClosed("valid canonical interest identifier required")
    with transaction.atomic():
        link = review_signed_existing_consent(
            actor=actor, interest_pk=interest_pk, inquiry=inquiry,
            consent_attestation=consent_attestation,
            consent_tag_hex=consent_tag_hex, consent_key=consent_key,
            request_ref=request_ref, inquiry_sha256=inquiry_sha256,
            consent_evidence_sha256=consent_evidence_sha256,
        )
        now = timezone.now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise Plan1OrderGateClosed("trusted server clock required")
        return review_existing_demo_interest_otp(
            consent_link=link, signed_otp_receipt=signed_otp_receipt,
            otp_tag_hex=signed_otp_tag_hex,
            trusted_otp_service_key=trusted_otp_service_key,
            trusted_consent_service_key=consent_key,
            declared_country=declared_country,
            age_18_self_attested=age_18_self_attested,
            server_now_sec=int(now.timestamp()),
        )
