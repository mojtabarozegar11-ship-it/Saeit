"""Authenticated display projection from reconciled evidence only.

No financial mutation. Every verified observation is checked for historical
breaches; missing session-open data and incomplete reconciliation fail closed.
"""
from collections import defaultdict
from django.db.models import F
from datetime import timedelta
from datetime import timezone as utc_timezone
from django.utils import timezone as django_timezone
from .periods import most_recent_completed_period, period_statistics
from decimal import Decimal

from .models import PropAccount, PropEquityObservation, PropExecution, PropSocialEvidence
from .social_policy import check_social_posting, LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION
from .trade_count import count_challenge_trades
from .plans import plan_for_code
from .rules import (
    POLICY, LEVELS, RiskDecision, assess_risk, assess_challenge, assess_promotion,
)

ZERO = Decimal("0")


def _day(value):
    return value.astimezone(utc_timezone.utc).date()


def completed_paid_phase_one_before_stage_two(account, *, as_of=None):
    """Only an earlier, independently reconciled same-contract phase qualifies.

    Do not allow a PASSED flag written after stage two began, a different
    purchase, or a phase opened before its settled purchase to unlock stage 2.
    This is eligibility evidence ONLY: it neither starts trading nor funds.
    """
    if (not isinstance(account, PropAccount)
            or account.kind != PropAccount.Kind.PHASE_TWO
            or not account.pk or account.opened_at is None
            or account.opened_at.tzinfo is None):
        return False
    # A v1.2 paid enrollment must never be relabelled as a legacy v1.1
    # trial to bypass the 50-position, 28-day and social-contract gates.
    # Legacy trials without any purchase retain their historical behaviour.
    if (account.challenge_enrollment_id is not None
            and account.policy_version != NEW_CONTRACT_VERSION):
        return False
    cutoff = as_of
    if cutoff is not None and (
            cutoff.tzinfo is None or cutoff.utcoffset() is None
            or account.opened_at > cutoff):
        return False
    q = account.trader.accounts.filter(
        kind=PropAccount.Kind.PHASE_ONE,
        status=PropAccount.Status.PASSED,
        reconciled_by_operator=True,
        policy_version=account.policy_version,
        opened_at__isnull=False,
        closed_at__isnull=False,
        opened_at__lte=F("closed_at"),
        closed_at__lte=account.opened_at,
    ).exclude(pk=account.pk)
    if cutoff is not None:
        q = q.filter(closed_at__lte=cutoff)
    if account.policy_version == NEW_CONTRACT_VERSION:
        purchase = account.challenge_enrollment
        if (purchase is None or purchase.trader_id != account.trader_id
                or purchase.settlement_verified is not True
                or purchase.terms_version != NEW_CONTRACT_VERSION):
            return False
        try:
            start = purchase.confirmed_at
            end = start + timedelta(days=POLICY.completion_deadline_days)
        except (ValueError, TypeError, OverflowError):
            return False
        if (start is None or start.tzinfo is None or start.utcoffset() is None
                or not start <= account.opened_at < end):
            return False
        q = q.filter(
            challenge_enrollment=purchase,
            starting_capital_usd=account.starting_capital_usd,
            tier_index=account.tier_index,
            opened_at__gte=start,
            closed_at__lt=end,
        )
    return q.exists()


def account_projection(account, *, as_of=None, evidence_cutoff=None):
    """Return verified-only account facts. No unverified data enters calculations."""
    if not isinstance(account, PropAccount) or not account.pk:
        raise ValueError("Persisted PropAccount required")

    # A past period must never be evaluated against transactions booked later.
    # A read-only projection must never book future broker data as completed
    # P&L or allow a historical report to look ahead at later executions.
    # An explicit historical cutoff stays exclusive, matching its contract.
    present = django_timezone.now()
    if as_of is not None:
        if getattr(as_of, "tzinfo", None) is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
    if evidence_cutoff is not None:
        if getattr(evidence_cutoff, "tzinfo", None) is None or evidence_cutoff.utcoffset() is None:
            raise ValueError("evidence_cutoff must be timezone-aware")
    effective_as_of = min(present, as_of) if as_of is not None else present
    effective_cutoff = min(
        effective_as_of, evidence_cutoff
    ) if evidence_cutoff is not None else effective_as_of
    source_executions = PropExecution.objects.filter(account=account)
    source_equity = PropEquityObservation.objects.filter(account=account)
    # Future-dated VERIFIED evidence is a reconciliation defect, not a new
    # trade; it must not qualify even when enough earlier trades exist.
    future_verified_evidence = (
        source_executions.filter(
            reconciliation_status="verified", closed_at__gt=present
        ).exists()
        or source_equity.filter(
            reconciliation_status="verified", observed_at__gt=present
        ).exists()
    )
    all_executions = source_executions.filter(closed_at__lte=effective_cutoff)
    all_equity = source_equity.filter(observed_at__lte=effective_cutoff)
    if evidence_cutoff is not None:
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
        and not future_verified_evidence
        and account.status not in {PropAccount.Status.BREACHED, PropAccount.Status.CLOSED}
        and account.policy_version in (LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION)
        and bool(executions)
    )
    assessment = None
    promotion_period = None
    promotion_stats = None
    social_decision = None
    challenge_trade_count = None
    purchase = account.challenge_enrollment if account.kind in (
        PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO
    ) else None
    # Fail closed when a paid enrollment is downgraded to the legacy contract.
    # Without this guard the v1.1 assessment path omits v1.2 trade/social
    # conditions and can mark an already paid challenge as eligible.
    purchase_window_valid = not (
        purchase is not None and (
            account.policy_version != NEW_CONTRACT_VERSION
            or purchase.terms_version != NEW_CONTRACT_VERSION
        )
    )
    selected_plan = None
    if purchase is not None:
        try:
            selected_plan = plan_for_code(purchase.plan_code)
        except ValueError:
            selected_plan = None
    if (account.policy_version == NEW_CONTRACT_VERSION and account.kind in (
            PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO)):
        purchase_window_valid = bool(
            purchase and selected_plan
            and account.starting_capital_usd == selected_plan.starting_capital_usd
            and account.tier_index == selected_plan.starting_tier_index
            and purchase.trader_id == account.trader_id
            and purchase.settlement_verified is True
            and purchase.terms_version == NEW_CONTRACT_VERSION
            and getattr(purchase.confirmed_at, "tzinfo", None) is not None
            and purchase.confirmed_at.utcoffset() is not None
            and purchase.confirmed_at <= effective_cutoff
        )
        if purchase_window_valid:
            start = purchase.confirmed_at
            end = start + timedelta(days=POLICY.completion_deadline_days)
            # Every broker event must be inside the four-week TRADING window.
            # Invalid events cannot be silently excluded to improve results.
            if any(not start <= event.closed_at < end for event in executions):
                purchase_window_valid = False
            # Equity snapshots are also broker evidence, not just executions.
            # Post-deadline or pre-payment equity must not be used to qualify
            # a 28-day challenge, even when the final P&L appears favourable.
            if any(not start <= mark.observed_at < end for mark in snapshots):
                purchase_window_valid = False
            # A verified account lifecycle must bound *both* execution and
            # marked-equity observations. Otherwise a close booked before the
            # stage opened, or after it was closed, could still qualify.
            # Legacy rows without lifecycle dates remain governed by separate
            # independent attestation/restore gates; this does not invent dates.
            opened = account.opened_at
            closed = account.closed_at
            if opened is not None:
                if (opened.tzinfo is None or opened.utcoffset() is None
                        or opened < start or opened >= end
                        or any(event.closed_at < opened for event in executions)
                        or any(mark.observed_at < opened for mark in snapshots)):
                    purchase_window_valid = False
            if closed is not None:
                if (closed.tzinfo is None or closed.utcoffset() is None
                        or not start <= closed < end
                        or (opened is not None and
                            opened.tzinfo is not None and
                            opened.utcoffset() is not None and closed < opened)
                        or any(event.closed_at > closed for event in executions)
                        or any(mark.observed_at > closed for mark in snapshots)):
                    purchase_window_valid = False
            cohort_executions = PropExecution.objects.filter(
                account__challenge_enrollment=purchase,
                account__kind__in=(PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO),
            )
            # The cohort-wide count must use the SAME temporal ceiling as
            # P&L/risk. Otherwise the other phase can supply a future 50th
            # trade even when this account's events are correctly filtered.
            cohort_executions = cohort_executions.filter(
                closed_at__lte=effective_cutoff
            )
            if evidence_cutoff is not None:
                cohort_executions = cohort_executions.filter(closed_at__lt=evidence_cutoff)
            challenge_trade_count = count_challenge_trades(
                cohort_executions, paid_at=start,
                required=POLICY.min_closed_trades_per_challenge,
            )
            social_records = PropSocialEvidence.objects.filter(
                enrollment=purchase,
                review_status=PropSocialEvidence.Review.VERIFIED,
            ).select_related("reviewed_by")
            if evidence_cutoff is not None:
                social_records = social_records.filter(
                    posted_at__lt=evidence_cutoff, reviewed_at__lt=evidence_cutoff
                )
            social_decision = check_social_posting(
                purchase_confirmed_at=start,
                as_of=effective_as_of,
                verified_posts=[{
                    "platform": item.platform,
                    "post_url": item.post_url,
                    "posted_at": item.posted_at,
                    "reviewed_at": item.reviewed_at,
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
                    "continued_visibility_verified": item.continued_visibility_verified,
                } for item in social_records],
            )
        # There is only one set of two social posts per paid enrollment shared
        # by both simulated phases. An absent purchase never creates readiness.
    if risk is not None:
        if account.kind in (PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO):
            prior = completed_paid_phase_one_before_stage_two(
                account, as_of=evidence_cutoff
            )
            assessment = assess_challenge(
                phase=1 if account.kind == PropAccount.Kind.PHASE_ONE else 2,
                account_capital=account.starting_capital_usd,
                realized_net_profit=total_net,
                trading_days=days,
                max_profitable_day=best_day,
                risk=risk,
                evidence_verified=bool(fully_verified and purchase_window_valid),
                prior_phase_passed=prior,
                social_posts_verified=(
                    social_decision.satisfied if social_decision is not None else False
                ),
                contract_version=account.policy_version,
                verified_cumulative_trades=(
                    challenge_trade_count.valid_closed_positions
                    if challenge_trade_count is not None else 0
                ),
            )
        elif account.kind == PropAccount.Kind.FUNDED:
            # Never reuse lifetime P&L to qualify a specific monthly promotion.
            promotion_period = most_recent_completed_period(
                opened_at=account.opened_at,
                as_of=effective_as_of,
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
        "challenge_trade_count": challenge_trade_count,
        "purchase_window_valid": purchase_window_valid,
        "challenge_purchase": purchase,
        "selected_plan": selected_plan,
        "plan_code": selected_plan.code if selected_plan else None,
        "promotion_period": promotion_period,
        "promotion_statistics": promotion_stats,
        # A reconciled trade stream does not authenticate its purchase.
        # Expose a verified/reconciled challenge only if the paid enrollment,
        # tier, chronology and 28-day evidence window ALSO pass review.
        "verified": bool(fully_verified and purchase_window_valid),
        "evidence_state": (
            "reconciled" if fully_verified and purchase_window_valid else "pending"
        ),
        "last_equity": equity.equity_usd if equity else None,
        "last_observed_at": equity.observed_at if equity else None,
        "executions": executions[:30],
        "policy_version": account.policy_version,
        "next_tier": LEVELS[min(account.tier_index + 1, len(LEVELS)-1)]
                     if account.kind == PropAccount.Kind.FUNDED else None,
        "no_payout_or_trade": True,
    }
