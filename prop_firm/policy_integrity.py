"""Canonical MOJ PROP contract fingerprint across the live-policy modules.

Prevents accidental release of a shadow nine-tier / single-stage policy.
This is an internal deterministic integrity guard, not broker, owner,
regulatory or funding attestation. It cannot authorize real orders.
"""
from __future__ import annotations

from decimal import Decimal
from .rules import LEVELS, POLICY
from .plans import CHALLENGE_PLANS, ALL_PLANS_SELLABLE


CANONICAL_CONTRACT_ID = "moj-prop-2026-11-15-v1.2-14level-two-stage"


def policy_drift_defects() -> tuple[str, ...]:
    """Return invariant breaches from the one authoritative policy snapshot."""
    expected_levels = tuple(Decimal(n) for n in (
        "100", "200", "400", "800", "1500", "3000", "5000", "10000",
        "20000", "35000", "50000", "70000", "85000", "100000",
    ))
    required = {
        "14_level_ladder": LEVELS == expected_levels,
        "ten_plans": len(CHALLENGE_PLANS) == 10,
        "single_owner_active_plan": (
            sum(p.business_active_owner_declared is True for p in CHALLENGE_PLANS) == 1
            and CHALLENGE_PLANS[0].business_active_owner_declared is True
        ),
        "nine_owner_funding_holds": all(
            p.temporary_owner_hold is True for p in CHALLENGE_PLANS[1:]
        ),
        "plan_one_entry_30_trx": (
            CHALLENGE_PLANS[0].entry_fee_trx == Decimal("30")
            and CHALLENGE_PLANS[0].starting_capital_usd == Decimal("100")
        ),
        "two_stage_targets": (
            POLICY.phase_one_goal_pct == Decimal("9.6")
            and POLICY.phase_two_goal_pct == Decimal("6")
        ),
        "daily_loss_4pct": POLICY.max_daily_loss_pct == Decimal("4"),
        "total_loss_8pct": POLICY.max_total_loss_pct == Decimal("8"),
        "risk_order_08pct": POLICY.order_risk_pct == Decimal("0.8"),
        "risk_aggregate_16pct": POLICY.aggregate_risk_pct == Decimal("1.6"),
        "consistency_32pct": POLICY.best_day_share_pct == Decimal("32"),
        "fifty_verified_closures": POLICY.min_closed_trades_per_challenge == 50,
        "twenty_eight_day_deadline": POLICY.completion_deadline_days == 28,
        "minimum_six_trading_days": POLICY.min_challenge_days == 6,
        "profit_split_70_30": (
            POLICY.trader_profit_share_pct == Decimal("70")
            and POLICY.company_profit_share_pct == Decimal("30")
        ),
        "single_mojtaba_bot": POLICY.canonical_bot == "mojtaba.bot.ai",
        "payments_and_orders_not_enabled": (
            POLICY.real_orders_enabled is False
            and POLICY.trx_checkout_enabled is False
            and ALL_PLANS_SELLABLE is False
            and all(p.checkout_enabled is False for p in CHALLENGE_PLANS)
        ),
        "ten_plan_stage_consistency": all(
            p.stage_one_profit_target_pct == POLICY.phase_one_goal_pct
            and p.stage_two_profit_target_pct == POLICY.phase_two_goal_pct
            and p.daily_loss_limit_pct == POLICY.max_daily_loss_pct
            and p.total_loss_limit_pct == POLICY.max_total_loss_pct
            and p.duration_days == POLICY.completion_deadline_days
            and p.minimum_verified_closed_trades == POLICY.min_closed_trades_per_challenge
            for p in CHALLENGE_PLANS
        ),
    }
    return tuple(name for name, met in required.items() if not met)


def policy_integrity_report() -> dict:
    defects = policy_drift_defects()
    return {
        "canonical_contract_id": CANONICAL_CONTRACT_ID,
        "policy_source": "prop_firm.rules.POLICY",
        "plan_source": "prop_firm.plans.CHALLENGE_PLANS",
        "checked_invariants": 18,
        "defects": list(defects),
        "source_policy_consistent": not defects,
        "external_funding_or_broker_verified": False,
        "payment_or_trading_authorized": False,
    }
