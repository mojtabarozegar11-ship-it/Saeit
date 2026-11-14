"""Private, read-only trader ledger projection.

No account creation, mutation, broker orders or payouts. Never evaluate a phase
as passed unless reconciled evidence and equity observation are both present.
"""
from collections import defaultdict
from datetime import timezone as utc_timezone
from decimal import Decimal

from .models import PropAccount, PropEquityObservation, PropExecution
from .rules import (
    POLICY, LEVELS, assess_risk, assess_challenge, assess_promotion,
)

ZERO = Decimal("0")


def _day(value):
    return value.astimezone(utc_timezone.utc).date()


def account_projection(account):
    """Return a display-only representation, derived from server-owned records."""
    if not isinstance(account, PropAccount) or not account.pk:
        raise ValueError("Persisted PropAccount required")

    executions = list(
        PropExecution.objects.filter(account=account, reconciliation_status="verified")
        .order_by("-closed_at", "-pk")
    )
    day_totals = defaultdict(lambda: ZERO)
    total_net = ZERO
    for event in executions:
        net = event.net_realized_usd
        day_totals[_day(event.closed_at)] += net
        total_net += net
    best_day = max([ZERO, *day_totals.values()])
    days = len(day_totals)

    # This is a *snapshot check*, not proof that historical volatility never breached.
    snapshots = list(
        PropEquityObservation.objects.filter(
            account=account, reconciliation_status="verified")
        .order_by("-observed_at", "-pk")[:30]
    )
    equity = snapshots[0] if snapshots else None
    session_open = next((
        snapshot for snapshot in snapshots
        if equity and snapshot.is_session_open
        and _day(snapshot.observed_at) == _day(equity.observed_at)
        and snapshot.observed_at <= equity.observed_at
    ), None)
    risk = None
    if equity is not None and session_open is not None:
        risk = assess_risk(
            account_capital=account.starting_capital_usd,
            equity=equity.equity_usd,
            day_open_equity=session_open.equity_usd,
        )

    phase_label = {
        PropAccount.Kind.PHASE_ONE: "Phase I",
        PropAccount.Kind.PHASE_TWO: "Phase II",
        PropAccount.Kind.FUNDED: "Company-funded",
    }.get(account.kind, "Unknown")

    # Reconciliation must be positive and valid, even if the account says passed.
    fully_verified = bool(
        account.reconciled_by_operator and risk is not None
        and account.status not in {PropAccount.Status.BREACHED, PropAccount.Status.CLOSED}
        and account.policy_version == POLICY.version
        and bool(executions)
    )
    result = None
    if risk is not None:
        if account.kind in (PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO):
            prior = account.trader.accounts.filter(
                kind=PropAccount.Kind.PHASE_ONE,
                status=PropAccount.Status.PASSED,
                reconciled_by_operator=True,
                policy_version=POLICY.version,
            ).exclude(pk=account.pk).exists()
            result = assess_challenge(
                phase=1 if account.kind == PropAccount.Kind.PHASE_ONE else 2,
                account_capital=account.starting_capital_usd,
                realized_net_profit=total_net,
                trading_days=days,
                max_profitable_day=best_day,
                risk=risk,
                evidence_verified=fully_verified,
                prior_phase_passed=prior,
            )
        else:
            # No treasury funding signoff is currently exposed. Never auto-promote.
            result = assess_promotion(
                level_index=account.tier_index,
                realized_monthly_profit=total_net,
                trading_days=days,
                max_profitable_day=best_day,
                risk=risk,
                evidence_verified=fully_verified,
                funding_for_next_level=False,
            )

    # No payout estimate is shown: cumulative allocations and signed approvals
    # must first be linked to a durable journal to prevent double credit.
    return {
        "account": account,
        "label": phase_label,
        "tier_capital": LEVELS[account.tier_index] if account.kind == PropAccount.Kind.FUNDED
                        else account.starting_capital_usd,
        "net_profit": total_net,
        "trading_days": days,
        "best_day": best_day,
        "risk": risk,
        "assessment": result,
        "verified": fully_verified,
        "evidence_state": "reconciled" if fully_verified else "pending",
        "last_equity": equity.equity_usd if equity else None,
        "last_observed_at": equity.observed_at if equity else None,
        "executions": executions[:30],
        "policy_version": account.policy_version,
        "next_tier": LEVELS[min(account.tier_index + 1, len(LEVELS)-1)]
                     if account.kind == PropAccount.Kind.FUNDED else None,
        "no_payout_or_trade": True,
    }
