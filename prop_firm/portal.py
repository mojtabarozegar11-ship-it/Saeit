"""Authenticated display projection from reconciled evidence only.

No financial mutation. Every verified observation is checked for historical
breaches; missing session-open data and incomplete reconciliation fail closed.
"""
from collections import defaultdict
from datetime import timezone as utc_timezone
from django.utils import timezone as django_timezone
from .periods import most_recent_completed_period, period_statistics
from decimal import Decimal

from .models import PropAccount, PropEquityObservation, PropExecution, PropSocialEvidence
from .social_policy import check_social_posting, LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION
from .rules import (
    POLICY, LEVELS, RiskDecision, assess_risk, assess_challenge, assess_promotion,
)

ZERO = Decimal("0")


def _day(value):
    return value.astimezone(utc_timezone.utc).date()


def completed_prior_phase_one(account):
    """Phase-two requires the same trader's reconciled, COMPLETED first phase.

    Prevent future/replayed phase-one status from retrospectively satisfying
    a challenge. Contract-policy versions must match exactly.
    """
    if (not isinstance(account, PropAccount)
            or account.kind != PropAccount.Kind.PHASE_TWO
            or not account.pk or account.opened_at is None):
        return False
    return account.trader.accounts.filter(
        kind=PropAccount.Kind.PHASE_ONE,
        status=PropAccount.Status.PASSED,
        reconciled_by_operator=True,
        policy_version=account.policy_version,
        closed_at__isnull=False,
        closed_at__lte=account.opened_at,
    ).exclude(pk=account.pk).exists()


def account_projection(account, *, as_of=None, evidence_cutoff=None):
    """Return verified-only account facts. No unverified data enters calculations."""
    if not isinstance(account, PropAccount) or not account.pk:
        raise ValueError("Persisted PropAccount required")

    # A past period must never be evaluated against transactions booked later.
    all_executions = PropExecution.objects.filter(account=account)
    all_equity = PropEquityObservation.objects.filter(account=account)
    if evidence_cutoff is not None:
        if getattr(evidence_cutoff, "tzinfo", None) is None or evidence_cutoff.utcoffset() is None:
            raise ValueError("evidence_cutoff must be timezone-aware")
        all_executions = all_executions.filter(closed_at__lt=evidence_cutoff)
        all_equity = all_equity.filter(observed_at__lt=evidence_cutoff)
    executions = list(
        all_executions.filter(reconciliation_status="verified")
        .order_by("-closed_at", "-pk")
    )
    partial_trades = all_executions.exclude(reconciliation_status="verified").exists()
    partial_equity = all_equity.exclude(reconciliation_status="verified").exists()

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
        all_equity.filter(reconciliation_status="verified")
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
        and account.policy_version in (LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION)
        and bool(executions)
    )
    assessment = None
    promotion_period = None
    promotion_stats = None
    social_decision = None
    if account.kind in (PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO):
        social_records = PropSocialEvidence.objects.filter(
            account=account,
            review_status=PropSocialEvidence.Review.VERIFIED,
        ).select_related("reviewed_by")
        if evidence_cutoff is not None:
            social_records = social_records.filter(
                posted_at__lt=evidence_cutoff, reviewed_at__lt=evidence_cutoff
            )
        social_decision = check_social_posting(
            verified_trading_dates=set(day_totals),
            verified_posts=[{
                "trading_day": item.trading_day,
                "platform": item.platform,
                "post_url": item.post_url,
                "review_status": item.review_status,
                "reviewed_by_operator": bool(
                    item.reviewed_by_id and item.reviewed_at is not None
                    and item.reviewed_by.is_staff
                    and item.reviewed_by_id != account.trader.user_id
                ),
                "author_verified": item.author_verified,
                "public_visible": item.public_visible,
                "disclosure_verified": item.disclosure_verified,
                "content_compliant": item.content_compliant,
                "date_verified": item.date_verified,
            } for item in social_records],
        )
    if risk is not None:
        if account.kind in (PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO):
            prior = completed_prior_phase_one(account)
            assessment = assess_challenge(
                phase=1 if account.kind == PropAccount.Kind.PHASE_ONE else 2,
                account_capital=account.starting_capital_usd,
                realized_net_profit=total_net,
                trading_days=days,
                max_profitable_day=best_day,
                risk=risk,
                evidence_verified=fully_verified,
                prior_phase_passed=prior,
                social_posts_verified=(
                    social_decision.satisfied if social_decision is not None else False
                ),
                contract_version=account.policy_version,
            )
        elif account.kind == PropAccount.Kind.FUNDED:
            # Never reuse lifetime P&L to qualify a specific monthly promotion.
            promotion_period = most_recent_completed_period(
                opened_at=account.opened_at,
                as_of=django_timezone.now() if as_of is None else as_of,
            )
            promotion_stats = period_statistics(executions, promotion_period)
            if promotion_stats is not None:
                # Treasury has no configured approval integration: no auto-promotion.
                assessment = assess_promotion(
                    level_index=account.tier_index,
                    realized_monthly_profit=promotion_stats["net"],
                    trading_days=promotion_stats["trading_days"],
                    max_profitable_day=promotion_stats["best_day"],
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
        "social_posting": social_decision,
        "promotion_period": promotion_period,
        "promotion_statistics": promotion_stats,
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
