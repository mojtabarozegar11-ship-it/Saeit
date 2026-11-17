"""Proposed XAUUSD DEMO order risk math gated on the exact v1.4.1 stage.

This adapter does NOT submit orders. It reuses the carefully checked 3%/8%
XAUUSD preflight from unsigned v1.3 with an explicit v1.4.1 contract boundary.
All simulation and quote/source authentication must occur in a future trusted
service. 'mathematically_admissible' is NEVER a trade authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from .plan1_v14_social_or_50_terms import review_prospective_terms
from .plan1_v141_simulated_challenge_engine import ChallengeReplayDecision
from .xauusd_v13_preflight import (
    DRAFT_CONTRACT_VERSION, GoldOrderSnapshot, GoldReview,
    review_gold_order, exact,
)

MAX_EQUITY_AGE = timedelta(minutes=5)


@dataclass(frozen=True)
class V141DemoOrderReview:
    challenge_ref: str
    contract_version: str
    intended_phase: int
    order_risk_usd: Decimal
    all_open_risk_usd: Decimal
    math_admissible: bool
    blockers: tuple[str, ...]
    trusted_broker_or_simulator_authenticated: bool = False
    complete_open_positions_independently_reconciled: bool = False
    demo_order_submitted: bool = False
    real_broker_order_submitted: bool = False
    trading_enabled: bool = False
    checkout_enabled: bool = False
    customer_enrollment_authorized: bool = False
    capital_or_payout_authorized: bool = False


def review_v141_demo_order(*, challenge: ChallengeReplayDecision,
                           intended_phase: int,
                           order: GoldOrderSnapshot) -> V141DemoOrderReview:
    """Fail-closed review; v1.4.1 buyer terms never silently become v1.3 terms."""
    terms = review_prospective_terms()
    if (type(challenge) is not ChallengeReplayDecision
            or challenge.contract_version != terms.version
            or challenge.terms_sha256 != terms.contract_candidate_sha256):
        raise ValueError("exact prospective buyer contract-bound challenge required")
    if type(intended_phase) is not int or intended_phase not in (1,2):
        raise ValueError("only demo stage 1 or 2")
    if type(order) is not GoldOrderSnapshot:
        raise ValueError("typed reviewed XAUUSD order snapshot required")
    if order.product != terms.sku or order.contract_version != DRAFT_CONTRACT_VERSION:
        raise ValueError("explicit v1.4.1 -> vetted v1.3 mathematical risk bridge only")
    if any((
        challenge.fee_collection_authorized,
        challenge.paid_enrollment_authorized,
        challenge.real_broker_orders_authorized,
        challenge.payout_authorized,
        challenge.source_authenticity_independently_proven,
        challenge.ledger_completeness_independently_proven,
    )):
        raise ValueError("replayed data cannot grant external authorization")
    current = (challenge.phase_one if intended_phase == 1 else challenge.phase_two)
    blockers = []
    if challenge.state in ("SIMULATED_RISK_BREACHED", "SIMULATED_EVALUATION_EXPIRED"):
        blockers.append("stopped_or_expired_challenge")
    expected = ("SIMULATED_STAGE_ONE_IN_REVIEW" if intended_phase == 1
                else "SIMULATED_STAGE_TWO_IN_REVIEW")
    if challenge.state != expected:
        blockers.append("stage_not_currently_open_for_demo_risk_review")
    if intended_phase == 2 and challenge.phase_one.mathematical_pass is not True:
        blockers.append("stage_one_not_mathematically_completed")
    # Profit/day/consistency targets can remain incomplete during an ACTIVE
    # simulated stage. Ledger corruption, wrong sources, forged statuses or
    # mismatched equity may not be ignored just because the stage is open.
    critical_global = frozenset((
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
    if any(reason in critical_global for reason in challenge.blockers):
        blockers.append("unreconciled_challenge_ledger_or_source")
    permitted_incomplete = frozenset((
        f"phase_{intended_phase}_fewer_than_six_utc_trading_days",
        f"phase_{intended_phase}_profit_target_not_met",
        f"phase_{intended_phase}_best_day_consistency_exceeded",
        f"phase_{intended_phase}_acceptance_transition_not_recorded",
        f"phase_{intended_phase}_no_closed_positions",
        f"phase_{intended_phase}_equity_history_missing",
    ))
    if any(reason not in permitted_incomplete for reason in current.blockers):
        blockers.append("current_phase_audit_integrity_not_reconciled")
    if (current.latest_verified_equity_usd is None
            or current.latest_verified_day_open_usd is None
            or current.latest_equity_observed_at_utc is None):
        blockers.append("latest_reconciled_demo_equity_required")
    else:
        if (exact(order.equity, allow_zero=True) != current.latest_verified_equity_usd
                or exact(order.day_open_equity) != current.latest_verified_day_open_usd):
            blockers.append("order_equity_not_bound_to_latest_challenge_mark")
        mark_at = datetime.fromisoformat(current.latest_equity_observed_at_utc)
        current_time = datetime.fromisoformat(challenge.assessment_utc)
        if (type(order.assessed_at) is not datetime
                or order.assessed_at.tzinfo is None
                or order.assessed_at.utcoffset() is None):
            blockers.append("assessed_at_timezone_required")
        else:
            assessment = order.assessed_at.astimezone(timezone.utc)
            if assessment != current_time:
                blockers.append("assessed_at_does_not_match_challenge_snapshot")
            if not timedelta(0) <= assessment - mark_at <= MAX_EQUITY_AGE:
                blockers.append("stale_or_future_equity_mark")
    # Reuse native USD/ounce, lot-step, spread, fees, slippage, margin,
    # 3% single, 8% aggregate and tighter 4% daily / 8% total controls.
    pure_risk = review_gold_order(order)
    blockers.extend(pure_risk.reasons)
    return V141DemoOrderReview(
        challenge_ref=challenge.challenge_ref, contract_version=terms.version,
        intended_phase=intended_phase,
        order_risk_usd=pure_risk.order_risk_usd,
        all_open_risk_usd=pure_risk.open_risk_usd,
        math_admissible=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
    )
