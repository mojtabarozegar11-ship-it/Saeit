"""Source-only adapter for canonical PropInterest; no DB or buyer PII access.

The canonical v1.2 parent branch contains a PropInterest ORM row with only
email, plan_code, consent_version, language and status. That row by itself
does NOT prove opt-in for an individual contract, a KYC check, or that an
address belongs to the applicant. A separately trusted CRM reviewer must
attest the underlying row plus PURPOSE-SPECIFIC consent evidence.
This function refuses all payable invoice, contact and enrollment effects.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re

from .buyer_interest_form import UnverifiedInquiry
from .buyer_order_review import Plan1OrderGateClosed
from .plan1_intake_provenance import verify_server_issued_private_inquiry
from .plan1_private_order_draft import Plan1PrivateOrderReviewDraft
from .order_readiness import SKU, TERMS_VERSION

CONSENT_VERSION = "moj-prop-interest-v1"
CRM_SCHEMA = "mojprop.plan1.private-crm-link-v1"
PROVENANCE_SCOPE = "one_requested_plan1_contract_review_not_marketing"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST = re.compile(r"REQUEST-[A-Z0-9]{16,32}\Z")
_BUYER = re.compile(r"BUYER-[A-Z0-9]{16,32}\Z")
_LANG = frozenset({"en", "fa", "ar"})
_REQUIRED = frozenset((
    "schema", "crm_record_id", "plan_code", "consent_version", "status",
    "source_language", "buyer_ref", "request_ref", "inquiry_sha256",
    "contract_review_sha256", "consent_proof_sha256", "consent_scope",
    "consent_reviewed_at_sec",
))


@dataclass(frozen=True)
class PrivateCRMLink:
    crm_record_id: int
    request_ref: str
    sku: str
    consent_version: str
    inquiry_sha256: str
    contract_review_sha256: str
    consent_proof_sha256: str
    record_digest: str
    state: str = "PRIVATE_CRM_REVIEW_ONLY"
    subject_identity_independently_proven_by_this_code: bool = False
    crm_row_exists_in_database_proven_by_this_code: bool = False
    separate_opt_in_evidence_has_been_authenticated_by_code: bool = False
    legal_kyc_approved_by_this_code: bool = False
    contact_allowed: bool = False
    marketing_allowed: bool = False
    invoice_issued: bool = False
    payment_allowed: bool = False
    challenge_enrollment_created: bool = False


def verify_private_prop_interest_link(
    *, inquiry: UnverifiedInquiry, draft: Plan1PrivateOrderReviewDraft,
    crm_attestation: dict, signed_crm_hmac_hex: str, trusted_crm_key: bytes,
    intake_hmac_hex: str, trusted_intake_key: bytes,
    expected_crm_record_id: int, expected_request_ref: str,
    expected_buyer_ref: str, server_now_sec: int,
) -> PrivateCRMLink:
    """Provenance reconciliation only; never issue a payable invoice.

    CRM signer, intake signer and source of expected IDs must be independently
    protected. Even a valid MAC does not establish real DB existence or
    permission to contact; customer rights, age/country, and buyer identity
    remain separate trusted steps.
    """
    if type(draft) is not Plan1PrivateOrderReviewDraft:
        raise Plan1OrderGateClosed("verified nonpayable Plan1 review draft required")
    if (draft.sku != SKU or draft.terms_version != TERMS_VERSION
            or draft.state != "PRIVATE_NONPAYABLE_CONTRACT_REVIEW"
            or draft.payable is not False
            or draft.live_invoice_created is not False
            or draft.payment_instructions_present is not False
            or draft.enrollment_created is not False):
        raise Plan1OrderGateClosed("CRM source cannot elevate order into commerce")
    if type(expected_crm_record_id) is not int or expected_crm_record_id < 1:
        raise Plan1OrderGateClosed("server-owned positive CRM row ID required")
    if (type(expected_request_ref) is not str
            or _REQUEST.fullmatch(expected_request_ref) is None
            or type(expected_buyer_ref) is not str
            or _BUYER.fullmatch(expected_buyer_ref) is None):
        raise Plan1OrderGateClosed("server-owned canonical refs required")
    if (type(trusted_crm_key) is not bytes or len(trusted_crm_key) < 32
            or type(trusted_intake_key) is not bytes or len(trusted_intake_key) < 32
            or hmac.compare_digest(trusted_crm_key, trusted_intake_key)):
        raise Plan1OrderGateClosed("independent CRM signer required")
    if (type(crm_attestation) is not dict
            or set(crm_attestation) != _REQUIRED):
        raise Plan1OrderGateClosed("expected CRM snapshot missing")
    for key, value in crm_attestation.items():
        if type(value) is str:
            if not value.isascii() or not value.isprintable() or not 1 <= len(value) <= 160:
                raise Plan1OrderGateClosed(f"unsafe CRM attestation {key}")
        elif type(value) is not int:
            raise Plan1OrderGateClosed("CRM attestation has unsupported types")
    if (type(signed_crm_hmac_hex) is not str
            or _HASH.fullmatch(signed_crm_hmac_hex) is None):
        raise Plan1OrderGateClosed("CRM signature missing")
    message = json.dumps(
        crm_attestation, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")
    if len(message) > 4096:
        raise Plan1OrderGateClosed("CRM proof packet too large")
    signature = hmac.new(trusted_crm_key, message, "sha256").hexdigest()
    if not hmac.compare_digest(signature, signed_crm_hmac_hex):
        raise Plan1OrderGateClosed("CRM evidence signature invalid")

    fixed = {
        "schema": CRM_SCHEMA,
        "crm_record_id": expected_crm_record_id,
        "plan_code": SKU, "consent_version": CONSENT_VERSION,
        "status": "new",  # contacted/withdrawn cannot be silently reused
        "buyer_ref": expected_buyer_ref,
        "request_ref": expected_request_ref,
        "inquiry_sha256": draft.inquiry_sha256,
        "contract_review_sha256": draft.reviewer_packet_sha256,
        "consent_scope": PROVENANCE_SCOPE,
    }
    for key, wanted in fixed.items():
        if (type(crm_attestation[key]) is not type(wanted)
                or crm_attestation[key] != wanted):
            raise Plan1OrderGateClosed(f"CRM-to-order mismatch: {key}")
    if (type(crm_attestation["source_language"]) is not str
            or crm_attestation["source_language"] not in _LANG):
        raise Plan1OrderGateClosed("CRM source language unsupported")
    consent_hash = crm_attestation["consent_proof_sha256"]
    if (type(consent_hash) is not str
            or _HASH.fullmatch(consent_hash) is None
            or consent_hash == "0" * 64):
        raise Plan1OrderGateClosed("purpose-specific consent evidence missing")
    reviewed_at = crm_attestation["consent_reviewed_at_sec"]
    if (type(reviewed_at) is not int or type(server_now_sec) is not int
            or not 1_735_689_600 <= reviewed_at <= server_now_sec
            or server_now_sec - reviewed_at > 86_400
            or server_now_sec >= draft.expires_at_sec):
        raise Plan1OrderGateClosed("CRM approval stale or review draft expired")
    if draft.original_request_ref != expected_request_ref:
        raise Plan1OrderGateClosed("draft request mismatch")
    verify_server_issued_private_inquiry(
        inquiry=inquiry, signed_intake_hmac_hex=intake_hmac_hex,
        trusted_intake_key=trusted_intake_key,
        expected_request_ref=expected_request_ref,
        expected_inquiry_digest=draft.inquiry_sha256,
    )
    return PrivateCRMLink(
        crm_record_id=expected_crm_record_id,
        request_ref=expected_request_ref,
        sku=SKU,
        consent_version=CONSENT_VERSION,
        inquiry_sha256=draft.inquiry_sha256,
        contract_review_sha256=draft.reviewer_packet_sha256,
        consent_proof_sha256=consent_hash,
        record_digest=hashlib.sha256(message).hexdigest(),
    )
