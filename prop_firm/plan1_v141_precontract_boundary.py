"""Strict, nonpayable MOJ PROP v1.4.1 interest -> precontract handoff.

The historical v1.2 buyer order/consent pipeline MUST NOT accept this version
without a separately audited legal implementation. This is PURE code: no
contacts, personal identity, accounts, enrollment, invoice, trades or email.
No caller-supplied truth value can authorize checkout or account activity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from .plan1_v14_private_interest_review import UnverifiedV14Interest
from .plan1_v14_social_or_50_terms import review_prospective_terms

_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
BLOCKERS = (
    "broker_written_approval_absent",
    "social_financial_advertising_legal_approval_absent",
    "buyer_jurisdiction_and_age_independent_screening_absent",
    "buyer_specific_signed_terms_and_refund_policy_absent",
    "independent_company_funds_and_broker_custody_absent",
    "native_trx_settlement_and_refund_controls_unverified",
    "restorable_external_backup_unverified",
)
STATUS = "nonpayable_legal_precontract_review_only"


class PrecontractBoundaryClosed(ValueError):
    """An inquiry cannot be bound to the exact proposed contract."""


@dataclass(frozen=True)
class PrecontractHandoffV141:
    request_ref: str
    contract_version: str
    contract_sha256: str
    informational_request_received_at_utc: str
    blocker_codes: tuple[str, ...] = BLOCKERS
    state: str = STATUS
    identity_independently_verified: bool = False
    buyer_signed_terms_verified: bool = False
    broker_permission_proven: bool = False
    paid_invoice_authorized: bool = False
    checkout_authorized: bool = False
    challenge_enrollment_authorized: bool = False
    simulated_phase_completed: bool = False
    social_post_verified: bool = False
    real_orders_authorized: bool = False
    payouts_authorized: bool = False


def prepare_v141_nonpayable_precontract(*, inquiry: UnverifiedV14Interest,
                                       expected_request_ref: str,
                                       expected_comprehension_sha256: str,
                                       server_now: datetime) -> PrecontractHandoffV141:
    """Only bind exact version, digest, request and chronology; nothing else.

    expected_* must be retrieved by a trusted server independently of the
    caller. This method does NOT establish that server or verify a signature.
    One applicant may request information BEFORE taking a demo challenge or
    posting; neither 50 closes nor 28-day social proof is a prerequisite to
    asking for a PRIVATE contract review.
    """
    terms = review_prospective_terms()
    if type(inquiry) is not UnverifiedV14Interest:
        raise PrecontractBoundaryClosed("valid typed v1.4.1 interest required")
    if (type(expected_request_ref) is not str
            or inquiry.request_ref != expected_request_ref
            or type(expected_comprehension_sha256) is not str
            or _SHA256.fullmatch(expected_comprehension_sha256) is None
            or inquiry.redacted_comprehension_sha256 != expected_comprehension_sha256):
        raise PrecontractBoundaryClosed("original inquiry reference or digest differs")
    if (inquiry.sku != terms.sku or inquiry.terms_version != terms.version
            or inquiry.accepted_terms_sha256 != terms.contract_candidate_sha256
            or inquiry.state != "prospective_nonpayable_interest_only"):
        raise PrecontractBoundaryClosed("wrong SKU, contract version, or terms fingerprint")
    forbidden = (
        inquiry.identity_independently_verified,
        inquiry.age_independently_verified,
        inquiry.broker_permission_verified,
        inquiry.finance_and_advertising_law_cleared,
        inquiry.contract_signed,
        inquiry.paid_invoice_authorized,
        inquiry.enrollment_authorized,
        inquiry.real_orders_authorized,
        inquiry.automated_marketing_authorized,
    )
    if any(value is not False for value in forbidden):
        raise PrecontractBoundaryClosed("an unverified inquiry cannot assert financial authority")
    if (type(server_now) is not datetime or server_now.tzinfo is None
            or server_now.utcoffset() is None):
        raise PrecontractBoundaryClosed("server-owned timezone-aware clock required")
    try:
        received = datetime.fromisoformat(inquiry.received_at_utc)
    except (TypeError, ValueError) as exc:
        raise PrecontractBoundaryClosed("invalid original timestamp") from exc
    if received.tzinfo is None or received.utcoffset() is None:
        raise PrecontractBoundaryClosed("original inquiry lacks timezone")
    received_utc = received.astimezone(timezone.utc)
    now_utc = server_now.astimezone(timezone.utc)
    if received_utc > now_utc:
        raise PrecontractBoundaryClosed("request receipt from the future")
    if (type(inquiry.declared_country) is not str
            or re.fullmatch(r"[A-Z]{2}", inquiry.declared_country) is None):
        raise PrecontractBoundaryClosed("unknown declared country")
    # Never use a purely unverified buyer declaration to assert legal eligibility.
    return PrecontractHandoffV141(
        request_ref=expected_request_ref,
        contract_version=terms.version,
        contract_sha256=terms.contract_candidate_sha256,
        informational_request_received_at_utc=received_utc.isoformat(),
    )
