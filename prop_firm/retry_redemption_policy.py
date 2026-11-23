"""Fail-closed pure eligibility rules for MOJ PROP failed-challenge retry.

Not wired to checkout. The caller MUST fetch and lock authoritative rows and
atomically claim the single-use redemption in the isolated MOJPROP database.
This module never authorizes payment or issues a customer entitlement.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ChallengeOutcome(str, Enum):
    FAILED = "failed"
    PASSED = "passed"
    ACTIVE = "active"
    VOID = "void"


@dataclass(frozen=True)
class RetryEvidence:
    challenge_id: str
    identity_id: str
    outcome: ChallengeOutcome
    final_at: datetime | None
    redemption_used: bool
    dispute_open: bool
    original_payment_final: bool


class RetryNotEligible(ValueError):
    pass


def require_failed_retry(evidence: RetryEvidence, *, buyer_identity_id: str) -> str:
    """Return authoritative challenge id only for an unused final failure.

    All fields must come from locked server-side records, never from a client.
    This pure check does not reserve a redemption: unique DB constraint and
    atomic row locking are still required before returning a priced invoice.
    """
    if type(evidence) is not RetryEvidence:
        raise RetryNotEligible("authoritative retry evidence required")
    if type(buyer_identity_id) is not str or not buyer_identity_id.strip():
        raise RetryNotEligible("verified buyer identity required")
    if (type(evidence.identity_id) is not str
            or evidence.identity_id != buyer_identity_id):
        raise RetryNotEligible("retry identity mismatch")
    if type(evidence.challenge_id) is not str or not evidence.challenge_id.strip():
        raise RetryNotEligible("valid prior challenge required")
    if evidence.outcome is not ChallengeOutcome.FAILED:
        raise RetryNotEligible("only final failed challenges qualify")
    if (type(evidence.final_at) is not datetime
            or evidence.final_at.tzinfo is None
            or evidence.final_at.utcoffset() is None):
        raise RetryNotEligible("verified timezone-aware finality required")
    # A future-dated final result is not authoritative evidence of a completed
    # failed challenge. Reject it before allowing a discounted invoice.
    if evidence.final_at > datetime.now(timezone.utc):
        raise RetryNotEligible("challenge finality cannot be in the future")
    if (type(evidence.redemption_used) is not bool
            or type(evidence.dispute_open) is not bool
            or type(evidence.original_payment_final) is not bool):
        raise RetryNotEligible("invalid redemption evidence")
    if evidence.redemption_used or evidence.dispute_open or not evidence.original_payment_final:
        raise RetryNotEligible("retry is unavailable")
    return evidence.challenge_id
