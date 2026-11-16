"""MOJ-PROP-01: bind a private unverified inquiry to a signed legal review.

SOURCE-ONLY: no contacts, real identity verification, invoices, payment receipt,
challenge enrollment, trading account or funding activation. Both records
must originate from separate trusted, appropriately controlled producers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .buyer_interest_form import UnverifiedInquiry
from .buyer_order_review import (
    PrivateOrderCase, Plan1OrderGateClosed, evaluate_signed_plan1_request,
)
from .order_readiness import SKU, TERMS_VERSION


@dataclass(frozen=True)
class PrecontractHandoff:
    request_ref: str
    inquiry_digest: str
    review_digest: str
    buyer_ref: str
    seller_ref: str
    sku: str = SKU
    terms_version: str = TERMS_VERSION
    state: str = "private_provenance_review"
    actual_buyer_identity_verified_by_this_module: bool = False
    actual_seller_legal_status_verified_by_this_module: bool = False
    signed_customer_contract_proven_by_this_module: bool = False
    live_invoice_authorized: bool = False
    native_trx_settlement_confirmed: bool = False
    enrollment_created: bool = False
    marketing_allowed: bool = False


def bind_private_inquiry_to_signed_review(
    *, inquiry: UnverifiedInquiry, reviewed_packet: dict,
    reviewer_tag_hex: str, trusted_reviewer_key: bytes,
    expected_request_ref: str, expected_buyer_ref: str,
    expected_seller_ref: str, server_now_sec: int,
) -> PrecontractHandoff:
    """Require equality between exact buyer-request digest AND signed review.

    The HMAC key must originate from a separate, authenticated server-side
    reviewer. This pure function cannot check that real-world buyer documents
    exist, and must never be used as a release/payment approval.
    """
    if type(inquiry) is not UnverifiedInquiry:
        raise Plan1OrderGateClosed("untrusted or missing original inquiry")
    if (inquiry.request_ref != expected_request_ref
            or inquiry.sku != SKU or inquiry.terms_version != TERMS_VERSION
            or inquiry.state != "unverified_private_interest"
            or inquiry.allowed_to_contact is not False
            or inquiry.payment_allowed is not False
            or inquiry.challenge_enrollment_allowed is not False):
        raise Plan1OrderGateClosed("original inquiry scope or state differs")
    try:
        received = datetime.fromisoformat(inquiry.received_at)
        if received.tzinfo is None or received.utcoffset() is None:
            raise ValueError("missing timezone")
        received_at_sec = int(received.astimezone(timezone.utc).timestamp())
    except (TypeError, ValueError, OverflowError) as exc:
        raise Plan1OrderGateClosed("untrusted inquiry receipt time") from exc

    if (type(reviewed_packet) is not dict
            or type(reviewed_packet.get("requested_at_sec")) is not int
            or reviewed_packet["requested_at_sec"] != received_at_sec):
        raise Plan1OrderGateClosed("signed request time differs from original receipt")
    reviewed: PrivateOrderCase = evaluate_signed_plan1_request(
        packet=reviewed_packet,
        signed_tag_hex=reviewer_tag_hex,
        trusted_reviewer_key=trusted_reviewer_key,
        expected_request_ref=expected_request_ref,
        expected_buyer_ref=expected_buyer_ref,
        expected_seller_ref=expected_seller_ref,
        expected_inquiry_intent_sha256=inquiry.anonymous_intent_sha256,
        server_now_sec=server_now_sec,
    )
    if (reviewed.sku != SKU or reviewed.contract_version != TERMS_VERSION
            or reviewed.payable_invoice_created is not False
            or reviewed.challenge_enrollment_created is not False):
        raise Plan1OrderGateClosed("review unexpectedly permits financial side effect")
    return PrecontractHandoff(
        request_ref=reviewed.request_ref,
        inquiry_digest=inquiry.anonymous_intent_sha256,
        review_digest=reviewed.review_packet_sha256,
        buyer_ref=reviewed.buyer_ref,
        seller_ref=reviewed.seller_ref,
    )
