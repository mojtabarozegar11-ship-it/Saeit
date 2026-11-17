"""Pure, reviewable v1.4.1 simulated-challenge journal transition policy.

This policy is the deterministic core used inside the transactional Django
writer. Only the database can ensure atomicity; only an authorized external
simulator/contract/archive can prove authenticity. This module is nonpayable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from .plan1_v141_simulated_challenge_engine import ChallengeReplayDecision
from .plan1_v14_social_or_50_terms import review_prospective_terms

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_TERMINAL = frozenset((
    "SIMULATED_RISK_BREACHED", "SIMULATED_EVALUATION_EXPIRED",
    "BOTH_MATH_REVIEWS_PASSED_EXTERNAL_PROOF_REQUIRED",
))
_GENESIS = "PENDING_SIGNED_SIMULATOR_FEED"
_RECORDED_STATES = frozenset((
    "SIMULATED_STAGE_ONE_IN_REVIEW",
    "SIMULATED_STAGE_ONE_MATH_PASSED_WAITING_TRANSITION",
    "SIMULATED_STAGE_TWO_IN_REVIEW",
    "TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK",
)) | _TERMINAL

_CRITICAL_INPUT_BLOCKERS = frozenset((
    "unsupported_non_xauusd_close",
    "close_outside_evaluation_or_future",
    "close_outside_sequential_phase_window",
    "equity_outside_evaluation_or_future",
    "equity_outside_sequential_phase_window",
    "unreconciled_close_event",
    "unreconciled_equity_observation",
    "conflicting_duplicate_event_id",
    "conflicting_duplicate_equity_id",
    "cross_source_position_id_conflict",
    "position_reused_between_simulated_phases",
    "phase_two_started_without_phase_one_mathematical_pass",
))

_STAGE_TWO_PARENTS = frozenset((
    "SIMULATED_STAGE_ONE_MATH_PASSED_WAITING_TRANSITION",
    "SIMULATED_STAGE_TWO_IN_REVIEW",
    "TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK",
))


class JournalTransitionRejected(ValueError):
    """A signed full-snapshot replay cannot advance the durable journal."""


@dataclass(frozen=True)
class PreviousReplayState:
    challenge_ref: str
    contract_sha256: str
    sequence: int
    engine_state: str
    last_assessment_utc: datetime | None
    last_phase_one_accepted_utc: datetime | None
    last_phase_two_started_utc: datetime | None
    last_phase_two_completed_utc: datetime | None
    previous_receipt_sha256: str = ""
    last_phase_one_evidence_sha256: str = ""
    last_phase_two_evidence_sha256: str = ""


@dataclass(frozen=True)
class ReviewedReceiptTransition:
    new_sequence: int
    manifest_sha256: str
    replay_sha256: str
    receipt_sha256: str
    previous_receipt_sha256: str
    assessment_utc: datetime
    phase_one_accepted_utc: datetime | None
    phase_two_started_utc: datetime | None
    phase_two_completed_utc: datetime | None
    phase_one_evidence_sha256: str | None
    phase_two_evidence_sha256: str | None
    resulting_engine_state: str
    mathematical_only: bool = True
    paid_enrollment_authorized: bool = False
    broker_order_authorized: bool = False
    payout_authorized: bool = False


def _time(value, label):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise JournalTransitionRejected(label + " must be UTC-aware datetime")
    return value.astimezone(timezone.utc)


def _from_decision(value, label):
    if value is None:
        return None
    if type(value) is not str:
        raise JournalTransitionRejected(label + " must be ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise JournalTransitionRejected(label + " malformed") from exc
    return _time(parsed, label)


def calculate_v141_receipt_sha256(
    *, challenge_ref: str, sequence: int,
    manifest_sha256: str, replay_sha256: str,
    previous_receipt_sha256: str,
    reported_engine_state: str, as_of_utc: datetime,
) -> str:
    """Pure canonical digest for BOTH new receipts and database read-back.

    This authenticates mathematical receipt metadata against a stored hash,
    but a database administrator could rewrite an entire unanchored chain.
    An immutable off-host archive and independent checkpoints remain necessary.
    """
    if (type(challenge_ref) is not str
            or re.fullmatch(r"CHALLENGE-[A-Z0-9]{16,40}", challenge_ref) is None):
        raise JournalTransitionRejected("invalid receipt challenge reference")
    if type(sequence) is not int or not 1 <= sequence <= 1_000_000_000:
        raise JournalTransitionRejected("receipt sequence outside permitted range")
    for value, label in (
        (manifest_sha256, "manifest"),
        (replay_sha256, "replay"),
        (previous_receipt_sha256, "previous receipt"),
    ):
        if type(value) is not str or _SHA.fullmatch(value) is None:
            raise JournalTransitionRejected(label + " SHA256 is not canonical")
    if (type(reported_engine_state) is not str
            or reported_engine_state not in _RECORDED_STATES):
        raise JournalTransitionRejected("unknown recorded simulator state")
    assessment = _time(as_of_utc, "receipt assessment")
    blob = dict(
        domain="mojprop.v141.simulated-receipt-chain.v1",
        challenge_ref=challenge_ref, sequence=sequence,
        manifest_sha256=manifest_sha256, replay_sha256=replay_sha256,
        previous_receipt_sha256=previous_receipt_sha256,
        reported_engine_state=reported_engine_state,
        as_of_utc=assessment.isoformat(),
    )
    return sha256(json.dumps(
        blob, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")).hexdigest()


def decide_next_signed_replay_receipt(*, previous: PreviousReplayState,
                                      calculated: ChallengeReplayDecision,
                                      manifest_sha256: str,
                                      requested_sequence: int) -> ReviewedReceiptTransition:
    """Enforce one legal NEXT monotone DEMO checkpoint, with immutable transitions.

    This function is NOT a backend, and does not itself verify source keys,
    the prior DB row, broker session calendar, customer payment or funds.
    """
    terms = review_prospective_terms()
    if type(previous) is not PreviousReplayState or type(calculated) is not ChallengeReplayDecision:
        raise JournalTransitionRejected("typed state and challenge math required")
    if (previous.challenge_ref != calculated.challenge_ref
            or previous.contract_sha256 != terms.contract_candidate_sha256
            or calculated.terms_sha256 != terms.contract_candidate_sha256
            or calculated.contract_version != terms.version):
        raise JournalTransitionRejected("original challenge and contract fingerprint mismatch")
    if type(previous.sequence) is not int or not 0 <= previous.sequence <= 1_000_000_000:
        raise JournalTransitionRejected("invalid stored challenge sequence")
    if (type(requested_sequence) is not int
            or requested_sequence != previous.sequence + 1
            or requested_sequence > 1_000_000_000):
        raise JournalTransitionRejected("nonconsecutive replay sequence")
    if type(manifest_sha256) is not str or _SHA.fullmatch(manifest_sha256) is None:
        raise JournalTransitionRejected("noncanonical manifest digest")
    if type(calculated.snapshot_sha256) is not str or _SHA.fullmatch(calculated.snapshot_sha256) is None:
        raise JournalTransitionRejected("noncanonical replay digest")
    if previous.engine_state in _TERMINAL:
        raise JournalTransitionRejected("breached, expired or fully reviewed state is terminal")
    if previous.sequence == 0:
        if previous.engine_state != _GENESIS:
            raise JournalTransitionRejected("genesis cannot forge an already progressed status")
        if (previous.last_phase_one_evidence_sha256
                or previous.last_phase_two_evidence_sha256
                or previous.last_assessment_utc is not None
                or previous.last_phase_one_accepted_utc is not None
                or previous.last_phase_two_started_utc is not None
                or previous.last_phase_two_completed_utc is not None
                or previous.previous_receipt_sha256):
            raise JournalTransitionRejected("initial empty state is inconsistent")
        prior_hash = "0" * 64
    else:
        if previous.engine_state not in _RECORDED_STATES:
            raise JournalTransitionRejected("unrecognized persisted challenge state")
        if previous.last_phase_two_completed_utc is None and previous.last_phase_two_evidence_sha256:
            raise JournalTransitionRejected("uncompleted stage two has unexpected frozen evidence")
        if previous.last_phase_two_completed_utc is not None and (
                type(previous.last_phase_two_evidence_sha256) is not str
                or _SHA.fullmatch(previous.last_phase_two_evidence_sha256) is None):
            raise JournalTransitionRejected("completed stage two lacks frozen evidence fingerprint")
        if (previous.last_phase_one_accepted_utc is None
                and previous.last_phase_one_evidence_sha256):
            raise JournalTransitionRejected("unaccepted stage one has unexpected frozen evidence")
        if (previous.engine_state == "SIMULATED_STAGE_ONE_IN_REVIEW"
                and previous.last_phase_one_accepted_utc is not None):
            raise JournalTransitionRejected("in-review stage one cannot have an acceptance checkpoint")
        if previous.last_phase_one_accepted_utc is not None and (
                type(previous.last_phase_one_evidence_sha256) is not str
                or _SHA.fullmatch(previous.last_phase_one_evidence_sha256) is None):
            raise JournalTransitionRejected("accepted stage one lacks frozen evidence fingerprint")
        if (previous.engine_state in (
                "SIMULATED_STAGE_ONE_MATH_PASSED_WAITING_TRANSITION",
                "SIMULATED_STAGE_TWO_IN_REVIEW",
                "TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK",
        ) and previous.last_phase_one_accepted_utc is None):
            raise JournalTransitionRejected("checkpoint lacks a persisted phase-one acceptance")
        if (previous.engine_state in (
                "SIMULATED_STAGE_TWO_IN_REVIEW",
                "TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK",
        ) and previous.last_phase_two_started_utc is None):
            raise JournalTransitionRejected("stage-two checkpoint lacks persisted start")
        if (previous.last_assessment_utc is None
                or type(previous.previous_receipt_sha256) is not str
                or _SHA.fullmatch(previous.previous_receipt_sha256) is None):
            raise JournalTransitionRejected("stored sequence lacks durable head receipt")
        prior_hash = previous.previous_receipt_sha256
    assessed = _from_decision(calculated.assessment_utc, "assessment")
    if previous.last_assessment_utc is not None and (
        assessed <= _time(previous.last_assessment_utc, "last_assessment")):
        raise JournalTransitionRejected("replay assessment cannot go backward or stay unchanged")
    stage_one = _from_decision(calculated.phase_one_accepted_at_utc, "phase_one_accepted")
    stage_two = _from_decision(calculated.phase_two_started_at_utc, "phase_two_started")
    done = _from_decision(calculated.phase_two_completed_at_utc, "phase_two_completed")
    frozen = calculated.phase_one_frozen_evidence_sha256
    if stage_one is not None:
        if any(code in _CRITICAL_INPUT_BLOCKERS for code in calculated.blockers):
            raise JournalTransitionRejected("stage-one acceptance has unreconciled or conflicting event evidence")
        if (calculated.phase_one.mathematical_pass is not True
                or type(frozen) is not str or _SHA.fullmatch(frozen) is None):
            raise JournalTransitionRejected("stage-one acceptance lacks valid closed-stage evidence")
        if (previous.last_phase_one_evidence_sha256
                and previous.last_phase_one_evidence_sha256 != frozen):
            raise JournalTransitionRejected("previously accepted phase-one evidence changed")
    elif frozen is not None:
        raise JournalTransitionRejected("unaccepted stage one cannot have a frozen evidence digest")
    frozen_two = calculated.phase_two_frozen_evidence_sha256
    if done is not None:
        if (calculated.phase_math_complete is not True
                or calculated.phase_two.mathematical_pass is not True
                or any(code in _CRITICAL_INPUT_BLOCKERS for code in calculated.blockers)
                or type(frozen_two) is not str or _SHA.fullmatch(frozen_two) is None):
            raise JournalTransitionRejected("stage-two completion lacks validated trading evidence")
        if (previous.last_phase_two_evidence_sha256
                and previous.last_phase_two_evidence_sha256 != frozen_two):
            raise JournalTransitionRejected("previously completed phase-two evidence changed")
    elif frozen_two is not None:
        raise JournalTransitionRejected("uncompleted phase two cannot have frozen evidence")
    for old, new, label in (
        (previous.last_phase_one_accepted_utc, stage_one, "stage_one_accepted"),
        (previous.last_phase_two_started_utc, stage_two, "stage_two_started"),
        (previous.last_phase_two_completed_utc, done, "stage_two_completed"),
    ):
        if old is not None and _time(old, label) != new:
            raise JournalTransitionRejected(label + " historical timestamp changed or removed")
    if stage_two is not None:
        if previous.engine_state not in _STAGE_TWO_PARENTS:
            raise JournalTransitionRejected("stage two lacks prior independently reviewed stage-one checkpoint")
        if calculated.phase_one.mathematical_pass is not True:
            raise JournalTransitionRejected("stage one must remain mathematically passed")
    if done is not None and stage_two is None:
        raise JournalTransitionRejected("stage-two finalization without stage-two start")
    if (calculated.real_broker_orders_authorized is not False
            or calculated.paid_enrollment_authorized is not False
            or calculated.fee_collection_authorized is not False
            or calculated.payout_authorized is not False):
        raise JournalTransitionRejected("a DEMO calculation cannot carry financial authorization")
    digest = calculate_v141_receipt_sha256(
        challenge_ref=previous.challenge_ref,
        sequence=requested_sequence, manifest_sha256=manifest_sha256,
        replay_sha256=calculated.snapshot_sha256,
        previous_receipt_sha256=prior_hash,
        reported_engine_state=calculated.state, as_of_utc=assessed,
    )
    return ReviewedReceiptTransition(
        new_sequence=requested_sequence, manifest_sha256=manifest_sha256,
        replay_sha256=calculated.snapshot_sha256,
        previous_receipt_sha256=prior_hash, receipt_sha256=digest,
        assessment_utc=assessed,
        phase_one_accepted_utc=stage_one,
        phase_two_started_utc=stage_two,
        phase_two_completed_utc=done,
        phase_one_evidence_sha256=frozen,
        phase_two_evidence_sha256=frozen_two,
        resulting_engine_state=calculated.state,
    )
