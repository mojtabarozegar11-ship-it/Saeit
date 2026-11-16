"""MOJ-PROP-01: offline, nonpayable, contract-locked order REVIEW DRAFT.

This is NOT a customer invoice, a signed contract, KYC, settlement,
funded-account authorization, durable order reservation or a live checkout.
Its verified input is a server-held signed-review envelope from Cycle B.
Underlying legal papers and signatures must be separately verified by a
qualified, authorized reviewer. Never pass user-supplied verifier keys.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from .buyer_interest_form import UnverifiedInquiry
from .buyer_order_review import Plan1OrderGateClosed
from .buyer_precontract_chain import bind_private_inquiry_to_signed_review
from .order_readiness import SKU, TERMS_VERSION

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_DOCUMENT_BINDINGS = {
    "contract_pdf_sha256": "trusted_contract_pdf_sha256",
    "refund_rights_disclosure_sha256": "trusted_refund_rights_sha256",
    "buyer_signature_proof_sha256": "trusted_buyer_signature_sha256",
    "seller_signature_proof_sha256": "trusted_seller_signature_sha256",
    "seller_legal_proof_sha256": "trusted_seller_legal_sha256",
    "capital_reserve_proof_sha256": "trusted_funding_reserve_sha256",
    "broker_authorization_sha256": "trusted_broker_authorization_sha256",
}


@dataclass(frozen=True)
class Plan1PrivateOrderReviewDraft:
    """Immutable PRIVATE reviewer record; never provide as payment directions."""

    private_review_ref: str
    original_request_ref: str
    sku: str
    terms_version: str
    amount_sun: int
    token_symbol: str
    chain: str
    contract_pdf_sha256: str
    refund_disclosure_sha256: str
    buyer_signature_proof_sha256: str
    seller_signature_proof_sha256: str
    inquiry_sha256: str
    reviewer_packet_sha256: str
    expires_at_sec: int
    state: str = "PRIVATE_NONPAYABLE_CONTRACT_REVIEW"
    has_authentic_legal_signature_by_this_code: bool = False
    has_merchant_legal_clearance_by_this_code: bool = False
    has_unencumbered_capital_by_this_code: bool = False
    has_verified_KYC_by_this_code: bool = False
    live_invoice_created: bool = False
    payable: bool = False
    payment_instructions_present: bool = False
    settlement_verified: bool = False
    enrollment_created: bool = False
    buyer_contact_authorized: bool = False
    marketing_authorized: bool = False
    independent_database_uniqueness_still_required: bool = True
    external_legal_review_still_required: bool = True


def build_plan1_private_review_draft(
    *, inquiry: UnverifiedInquiry, reviewed_packet: dict,
    reviewer_tag_hex: str, trusted_reviewer_key: bytes,
    expected_request_ref: str, expected_buyer_ref: str,
    expected_seller_ref: str, server_now_sec: int,
    trusted_contract_pdf_sha256: str,
    trusted_refund_rights_sha256: str,
    trusted_buyer_signature_sha256: str,
    trusted_seller_signature_sha256: str,
    trusted_seller_legal_sha256: str,
    trusted_funding_reserve_sha256: str,
    trusted_broker_authorization_sha256: str,
) -> Plan1PrivateOrderReviewDraft:
    """Return only a contract-bound private review snapshot, never payable.

    All trusted_... arguments must be independently resolved from immutable,
    access-controlled files/records. Just supplying hashes from the browser
    or the packet itself would not prove legal validity of the documents.
    This function cannot guarantee durable uniqueness or revoke a quote.
    """
    handoff = bind_private_inquiry_to_signed_review(
        inquiry=inquiry, reviewed_packet=reviewed_packet,
        reviewer_tag_hex=reviewer_tag_hex,
        trusted_reviewer_key=trusted_reviewer_key,
        expected_request_ref=expected_request_ref,
        expected_buyer_ref=expected_buyer_ref,
        expected_seller_ref=expected_seller_ref,
        server_now_sec=server_now_sec,
    )
    trusted = {
        "trusted_contract_pdf_sha256": trusted_contract_pdf_sha256,
        "trusted_refund_rights_sha256": trusted_refund_rights_sha256,
        "trusted_buyer_signature_sha256": trusted_buyer_signature_sha256,
        "trusted_seller_signature_sha256": trusted_seller_signature_sha256,
        "trusted_seller_legal_sha256": trusted_seller_legal_sha256,
        "trusted_funding_reserve_sha256": trusted_funding_reserve_sha256,
        "trusted_broker_authorization_sha256": trusted_broker_authorization_sha256,
    }
    for key, expected_key in _DOCUMENT_BINDINGS.items():
        expected = trusted[expected_key]
        if (type(expected) is not str
                or _DIGEST.fullmatch(expected) is None
                or expected == "0" * 64
                or reviewed_packet["proofs"][key] != expected):
            raise Plan1OrderGateClosed(
                "trusted document digest missing or does not match signed review: " + key
            )
    if (handoff.sku != SKU or handoff.terms_version != TERMS_VERSION
            or handoff.live_invoice_authorized is not False
            or handoff.native_trx_settlement_confirmed is not False
            or handoff.enrollment_created is not False):
        raise Plan1OrderGateClosed("review handoff cannot authorize commerce")
    # Reviewed envelope is already HMAC-authenticated by the preceding call.
    expiry = reviewed_packet["expires_at_sec"]
    # A deterministic private review reference, not an invoice identifier.
    # Requires a later durable unique registry; do not use as proof of payment.
    case_material = json.dumps(
        {
            "purpose": "mojprop-plan1-contract-review-only",
            "request": handoff.request_ref,
            "buyer": handoff.buyer_ref,
            "seller": handoff.seller_ref,
            "inquiry": handoff.inquiry_digest,
            "review": handoff.review_digest,
            "contract": trusted_contract_pdf_sha256,
        },
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    private_ref = "PROP1-REVIEW-" + sha256(case_material).hexdigest()[:32].upper()
    return Plan1PrivateOrderReviewDraft(
        private_review_ref=private_ref,
        original_request_ref=handoff.request_ref,
        sku=SKU, terms_version=TERMS_VERSION,
        amount_sun=30_000_000, token_symbol="TRX", chain="TRON-mainnet",
        contract_pdf_sha256=trusted_contract_pdf_sha256,
        refund_disclosure_sha256=trusted_refund_rights_sha256,
        buyer_signature_proof_sha256=trusted_buyer_signature_sha256,
        seller_signature_proof_sha256=trusted_seller_signature_sha256,
        inquiry_sha256=handoff.inquiry_digest,
        reviewer_packet_sha256=handoff.review_digest,
        expires_at_sec=expiry,
    )
