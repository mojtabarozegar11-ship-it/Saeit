"""Pure NONPAYABLE XAUUSD v1.3 two-stage qualification preview.

Unlike historical v1.2, this draft does NOT require social-media posts.
It reuses the canonical trade ledger's deduplicated CLOSED-position counter;
never takes a buyer-supplied count as evidence. This is math-only review:
a positive result DOES NOT authorize an invoice, enrollment, account or trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .trade_count import count_challenge_trades
from .xauusd_v13_cross_source_guard import assess_closed_position_source_conflicts
from .xauusd_v13_draft_terms import draft_gold_terms_v13
from .xauusd_v13_preflight import DRAFT_CONTRACT_VERSION, exact


@dataclass(frozen=True)
class PhaseProof:
    phase: int
    realized_net_profit_usd: str
    max_profitable_day_usd: str
    verified_trading_days: int
    phase_evidence_verified: bool
    risk_limits_independently_reviewed: bool


@dataclass(frozen=True)
class QualificationPreview:
    sku: str
    contract_version: str
    reviewed_closed_positions: int
    required_closed_positions: int
    phase_one_math_pass: bool
    phase_two_math_pass: bool
    entire_challenge_math_pass: bool
    reasons: tuple[str, ...]
    social_post_evidence_required: bool = False
    terms_fully_reconciled: bool = False
    signed_customer_contract_proven: bool = False
    funds_independently_verified: bool = False
    paid_enrollment_authorized: bool = False
    broker_account_authorized: bool = False
    real_orders_authorized: bool = False
    payouts_authorized: bool = False


def _phase_reasons(phase: PhaseProof, expected_phase: int, target: Decimal,
                   minimum_days: int) -> tuple[str, ...]:
    if type(phase) is not PhaseProof or type(phase.phase) is not int or phase.phase != expected_phase:
        raise ValueError("phase identity mismatch")
    if type(phase.verified_trading_days) is not int or not 0 <= phase.verified_trading_days <= 28:
        raise ValueError("invalid verified trading day count")
    profit = exact(phase.realized_net_profit_usd, allow_zero=True)
    best = exact(phase.max_profitable_day_usd, allow_zero=True)
    reasons = []
    if phase.phase_evidence_verified is not True:
        reasons.append(f"phase_{expected_phase}_independent_proof_absent")
    if phase.risk_limits_independently_reviewed is not True:
        reasons.append(f"phase_{expected_phase}_risk_proof_absent")
    if phase.verified_trading_days < minimum_days:
        reasons.append(f"phase_{expected_phase}_minimum_trading_days_not_met")
    if profit < target:
        reasons.append(f"phase_{expected_phase}_profit_target_not_met")
    if best > profit * Decimal("0.32"):
        reasons.append(f"phase_{expected_phase}_consistency_not_met")
    return tuple(reasons)


def review_xauusd_v13_qualification(*, first: PhaseProof, second: PhaseProof,
                                   reconciled_executions, evaluation_started_at: datetime,
                                   immutable_ledger_complete: bool,
                                   independent_ledger_source_verified: bool,
                                   legal_terms_approved: bool = False) -> QualificationPreview:
    """Only compute preview of two demo phases, never sign off customer funding.

    The caller must obtain ledger and phase proofs from independent services.
    This function cannot authenticate those services, nor determine legal terms.
    The legal_terms_approved parameter is deliberately NOT an override:
    a signed, authorized contract requires a separate approved legal gate.
    """
    draft = draft_gold_terms_v13()
    if draft.contract_version != DRAFT_CONTRACT_VERSION or draft.sku != "MOJ-PROP-01":
        raise ValueError("unexpected signed-contract context")
    if type(reconciled_executions) not in (list, tuple) or len(reconciled_executions) > 1000:
        raise ValueError("bounded reconciled execution ledger required")
    if type(immutable_ledger_complete) is not bool or type(independent_ledger_source_verified) is not bool:
        raise ValueError("strict ledger provenance flags required")
    if legal_terms_approved is not False:
        # A form/API boolean can never authorize a contract change.
        raise ValueError("legal review cannot be self-approved by this preview")
    p1 = _phase_reasons(first, 1, Decimal("9.6"), draft.min_trading_days_per_stage)
    p2 = _phase_reasons(second, 2, Decimal("6"), draft.min_trading_days_per_stage)
    counts = count_challenge_trades(
        reconciled_executions, paid_at=evaluation_started_at,
        required=draft.min_closed_trades_total,
    )
    source_collisions = assess_closed_position_source_conflicts(
        reconciled_executions, evaluation_started_at=evaluation_started_at,
    )
    reasons = list(p1) + list(p2)
    if immutable_ledger_complete is not True:
        reasons.append("immutable_closed_trade_ledger_incomplete")
    if independent_ledger_source_verified is not True:
        reasons.append("independent_ledger_origin_unverified")
    if not counts.sufficient:
        reasons.append("minimum_50_unique_closed_positions_total_not_met")
    if source_collisions.collisions:
        reasons.append("cross_source_duplicate_position_review_required")
    if not p1 and p2:
        reasons.append("phase_two_unmet_after_phase_one")
    # Counterparty, contract, capital and funding readiness NEVER get cleared.
    math_pass = not reasons
    return QualificationPreview(
        sku=draft.sku,
        contract_version=draft.contract_version,
        reviewed_closed_positions=counts.valid_closed_positions,
        required_closed_positions=draft.min_closed_trades_total,
        phase_one_math_pass=not p1,
        phase_two_math_pass=not p2 and not p1,
        entire_challenge_math_pass=math_pass,
        reasons=tuple(dict.fromkeys(reasons)),
    )
