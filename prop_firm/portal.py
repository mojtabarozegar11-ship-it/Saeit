"""Authenticated display projection from reconciled evidence only.

No financial mutation. Every verified observation is checked for historical
breaches; missing session-open data and incomplete reconciliation fail closed.
"""
from collections import defaultdict
from datetime import timezone as utc_timezone
from decimal import Decimal

from .models import PropAccount, PropEquityObservation, PropExecution
from .rules import (
    POLICY, LEVELS, RiskDecision, assess_risk, assess_challenge, assess_promotion,
)

ZERO = Decimal("0")


def _day(value):
    return value.astimezone(utc_timezone.utc).date()


def account_projection(account):
    """Return verified-only account facts. No unverified data enters calculations."""
    if not isinstance(account, PropAccount) or not account.pk:
        raise ValueError("Persisted PropAccount required")

    executions = list(
        PropExecution.objects.filter(account=account, reconciliation_status="verified")
        .order_by("-closed_at", "-pk")
    )
    partial_trades = PropExecution.objects.filter(account=account).exclude(
        reconciliation_status="verified").exists()
    partial_equity = PropEquityObservation.objects.filter(account=account).exclude(
        reconciliation_status="verified").exists()

    day_totals = defaultdict(lambda: ZERO)
    total_net = ZERO
    for event in executions:
        net = event.net_realized_usd
        day_totals[_day(event.closed_at)] += net
        total_net += net
    best_day = max([ZERO, *day_totals.values()])
    days = len(day_totals)

    # Review the entire verified equity stream, not just the latest mark.
    # The operator must attest coverage of all session hours and positions.
    snapshots = list(
        PropEquityObservation.objects.filter(
            account=account, reconciliation_status="verified")
        .order_by("observed_at", "pk")
    )
    equity = snapshots[-1] if snapshots else None
    starts = {}
    reasons = []
    historical_breach = False
    for observation in snapshots:
        date = _day(observation.observed_at)
        if observation.is_session_open:
            if date in starts:
                reasons.append("duplicate_session_open")
            else:
                starts[date] = observation.equity_usd
        if date not in starts:
            reasons.append("missing_session_open")
            continue
        state = assess_risk(
            account_capital=account.starting_capital_usd,
            equity=observation.equity_usd,
            day_open_equity=starts[date],
        )
        if not state.allowed:
            historical_breach = True
            reasons.extend(state.reasons)

    if not set(day_totals).issubset(set(starts)):
        reasons.append("missing_trade_day_equity")
    latest_open = starts.get(_day(equity.observed_at)) if equity else None
    risk = None
    if equity is not None and latest_open is not None:
        result = assess_risk(
            account_capital=account.starting_capital_usd,
            equity=equity.equity_usd,
            day_open_equity=latest_open,
        )
        if reasons:
            risk = RiskDecision(
                allowed=False,
                reasons=tuple(dict.fromkeys((*result.reasons, *reasons))),
                daily_equity_floor=result.daily_equity_floor,
                total_equity_floor=result.total_equity_floor,
            )
        else:
            risk = result

    fully_verified = bool(
        account.reconciled_by_operator and risk is not None
        and not partial_trades and not partial_equity
        and not reasons and not historical_breach
        and account.status not in {PropAccount.Status.BREACHED, PropAccount.Status.CLOSED}
        and account.policy_version == POLICY.version
        and bool(executions)
    )
    assessment = None
    if risk is not None:
        if account.kind in (PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO):
            prior = account.trader.accounts.filter(
                kind=PropAccount.Kind.PHASE_ONE,
                status=PropAccount.Status.PASSED,
                reconciled_by_operator=True,
                policy_version=POLICY.version,
            ).exclude(pk=account.pk).exists()
            assessment = assess_challenge(
                phase=1 if account.kind == PropAccount.Kind.PHASE_ONE else 2,
                account_capital=account.starting_capital_usd,
                realized_net_profit=total_net,
                trading_days=days,
                max_profitable_day=best_day,
                risk=risk,
                evidence_verified=fully_verified,
                prior_phase_passed=prior,
            )
        elif account.kind == PropAccount.Kind.FUNDED:
            # Treasury has no configured approval integration; don't auto-promote.
            assessment = assess_promotion(
                level_index=account.tier_index,
                realized_monthly_profit=total_net,
                trading_days=days,
                max_profitable_day=best_day,
                risk=risk,
                evidence_verified=fully_verified,
                funding_for_next_level=False,
            )

    return {
        "account": account,
        "tier_capital": LEVELS[account.tier_index] if account.kind == PropAccount.Kind.FUNDED
                        else account.starting_capital_usd,
        "net_profit": total_net,
        "trading_days": days,
        "best_day": best_day,
        "risk": risk,
        "assessment": assessment,
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
