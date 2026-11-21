"""Hard, read-only commercial admission gate for new English Starter30 invoices.

A successful wallet/RPC preflight is NOT contract compliance or funded reward
settlement capacity. Fail closed on stale 32%/70:30 historical policy, absent
effective evaluator, incomplete approved rules, or missing externally reviewed
reserve and real disbursement evidence.

This module never emails, writes a database, signs, transfers, or trades.
All hold reasons are stable machine codes; no credentials/evidence refs leaked.
Existing historical paid invoices/refunds MUST be reconciled separately rather
than denied by the new-buyer admission gate.
"""
from __future__ import annotations

from decimal import Decimal
import re

from django.conf import settings

from .simulation_policy import SIMULATION_POLICY


class Starter30PaidAdmissionHold(ValueError):
    """Current source and attested business capacity cannot sell Starter30."""


_EVIDENCE_REF_PATTERN = re.compile(r"[A-Za-z0-9._:/-]{16,128}\Z")
_OWNER_GATES = (
    ("MPW_MOJPROP_PAID_RULES_FINALLY_APPROVED", "accepted_paid_rules_not_approved"),
    ("MPW_MOJPROP_WRITTEN_PAID_TERMS_VERIFIED", "accepted_terms_not_verified"),
    ("MPW_MOJPROP_QUALIFIED_PAYOUT_RESERVE_VERIFIED", "real_reward_reserve_unverified"),
    ("MPW_MOJPROP_REAL_REWARD_SETTLEMENT_VERIFIED", "real_payout_rail_unverified"),
)
_EXPECTED_POLICY = (
    ("starting_balance_usd", Decimal("1000")),
    ("challenge_window_days", 60),
    ("daily_loss_limit_pct", Decimal("6")),
    ("max_risk_per_trade_pct", Decimal("3")),
    ("max_open_risk_pct", Decimal("4")),
    ("canonical_best_day_share_pct", Decimal("50")),
    ("trader_eligible_profit_share_pct", Decimal("100")),
    ("company_eligible_profit_share_pct", Decimal("0")),
    ("first_payout_min_activity_days", 14),
    ("subsequent_payout_interval_days", 14),
    ("minimum_payout_request_usd", Decimal("10")),
    ("transfer_network_fees_paid_by_company", True),
    ("entry_fee_refund_with_first_successful_profit_withdrawal", True),
)
_EFFECTIVE_SCORER = (
    ("best_day_share_pct", Decimal("50")),
    ("trader_profit_share_pct", Decimal("100")),
    ("company_profit_share_pct", Decimal("0")),
    ("max_daily_loss_pct", Decimal("6")),
    ("order_risk_pct", Decimal("3")),
    ("aggregate_risk_pct", Decimal("4")),
    ("completion_deadline_days", 60),
    ("account_mode", "simulated"),
    ("payout_mode", "real_performance_reward"),
    ("real_orders_enabled", False),
)


def paid_admission_defects(*, check_attestations: bool = True) -> tuple[str, ...]:
    """Deterministic proof checklist, without requesting customer/payment data."""
    defects = []

    for name, expected in _EXPECTED_POLICY:
        if getattr(SIMULATION_POLICY, name, None) != expected:
            defects.append("new_offer_" + name + "_mismatch")

    # Main source historically has no legacy rules.py, while the effective
    # cPanel runtime DOES, and it still computes 32% consistency / 70:30 cash.
    # Absent source or import drift must block billing, not be overlooked.
    try:
        from prop_firm.rules import POLICY as effective
    except (ImportError, AttributeError):
        defects.append("effective_scoring_contract_unavailable")
    else:
        for name, expected in _EFFECTIVE_SCORER:
            if getattr(effective, name, None) != expected:
                defects.append("effective_scorer_" + name + "_mismatch")
        if getattr(effective, "version", None) != SIMULATION_POLICY.contract_version:
            defects.append("scoring_contract_version_mismatch")

    try:
        from .simulation_payout import PAYOUT_PERCENT
    except (ImportError, AttributeError):
        defects.append("verified_profit_commitment_calculator_unavailable")
    else:
        if PAYOUT_PERCENT != 100:
            defects.append("verified_profit_commitment_not_100_percent")

    if check_attestations:
        for name, reason in _OWNER_GATES:
            if getattr(settings, name, False) is not True:
                defects.append(reason)
        reference = getattr(settings, "MPW_MOJPROP_PAID_TERMS_EVIDENCE_REF", "")
        if (type(reference) is not str
                or _EVIDENCE_REF_PATTERN.fullmatch(reference) is None):
            defects.append("private_paid_terms_evidence_reference_missing")
        reserve_ref = getattr(settings, "MPW_MOJPROP_REWARD_RESERVE_EVIDENCE_REF", "")
        if (type(reserve_ref) is not str
                or _EVIDENCE_REF_PATTERN.fullmatch(reserve_ref) is None):
            defects.append("private_reward_reserve_evidence_reference_missing")
        rail_ref = getattr(settings, "MPW_MOJPROP_REWARD_SETTLEMENT_EVIDENCE_REF", "")
        if (type(rail_ref) is not str
                or _EVIDENCE_REF_PATTERN.fullmatch(rail_ref) is None):
            defects.append("private_real_settlement_evidence_reference_missing")

    return tuple(dict.fromkeys(defects))


def require_paid_admission_readiness() -> None:
    """Reject a NEW invoice before touching an identity, DB or blockchain."""
    errors = paid_admission_defects()
    if errors:
        raise Starter30PaidAdmissionHold(
            "Starter30 new payment admission is on hold until complete "
            "approved rules, a 100% trader reward engine, and real "
            "reward funding/settlement proof agree"
        )
