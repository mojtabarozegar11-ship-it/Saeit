"""Stage 70/30 provisional allocations from *verified* broker records only.

This is not an accounts-payable approval or transfer service. Nothing here
sends bank, TRX, wallet, broker, social, mail, or customer notifications.
"""
from decimal import Decimal
import hashlib
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    PropAccount, PropExecution, PropEquityObservation,
    PropProfitAllocation, PropProfitJournalLine,
)
from .periods import most_recent_completed_period, completed_period_by_number
from .portal import account_projection
from .rules import POLICY, calculate_payout


class AllocationRejected(ValueError):
    pass


def _verified_source(account, *, period_end):
    """Require signed evidence on *every* included broker row."""
    sources = getattr(settings, "MOJ_PROP_TRUSTED_EVIDENCE_KEYS", {})
    if not isinstance(sources, dict) or not sources:
        raise AllocationRejected("No trusted broker evidence sources configured")
    executions = list(
        PropExecution.objects.filter(account=account, closed_at__lt=period_end)
        .order_by("closed_at", "pk")
    )
    marks = list(
        PropEquityObservation.objects.filter(account=account, observed_at__lt=period_end)
        .order_by("observed_at", "pk")
    )
    if not executions or not marks:
        raise AllocationRejected("No complete broker trade/equity history")
    if any(
        event.reconciliation_status != "verified"
        or event.data_source not in sources
        or not re.fullmatch("[0-9a-f]{64}", event.evidence_digest or "")
        for event in executions
    ):
        raise AllocationRejected("Unverified or unsigned brokerage execution")
    if any(
        mark.reconciliation_status != "verified"
        or mark.data_source not in sources
        or not re.fullmatch("[0-9a-f]{64}", mark.evidence_digest or "")
        for mark in marks
    ):
        raise AllocationRejected("Unverified brokerage equity evidence")
    # Signing keys from separate providers do not make their records one
    # continuous funded account. Mixing brokers can double count equity or
    # conceal losses even when every row was individually signed.
    execution_sources = {event.data_source for event in executions}
    mark_sources = {mark.data_source for mark in marks}
    if len(execution_sources) != 1 or mark_sources != execution_sources:
        raise AllocationRejected("Funded brokerage source continuity mismatch")
    return executions, marks


def _journal_is_balanced(allocation):
    rows = list(allocation.journal_lines.all())
    if allocation.eligible_profit_usd == 0:
        return not rows
    debit = sum((j.amount_usd for j in rows if j.side == "debit"), Decimal("0"))
    credit = sum((j.amount_usd for j in rows if j.side == "credit"), Decimal("0"))
    types = {j.code for j in rows}
    expected = {"pool_debit"}
    if allocation.trader_profit_usd:
        expected.add("trader_credit")
    if allocation.company_profit_usd:
        expected.add("company_credit")
    target = {
        "pool_debit": ("debit", allocation.eligible_profit_usd),
        "trader_credit": ("credit", allocation.trader_profit_usd),
        "company_credit": ("credit", allocation.company_profit_usd),
    }
    correctly_typed = all(
        line.side == target[line.code][0]
        and line.amount_usd == target[line.code][1]
        for line in rows if line.code in target
    )
    return (
        debit == credit == allocation.eligible_profit_usd
        and types == expected
        and len(rows) == len(expected)
        and correctly_typed
        and allocation.trader_profit_usd + allocation.company_profit_usd
            == allocation.eligible_profit_usd
    )


@transaction.atomic
def stage_provisional_allocation(*, account_id, as_of=None, period_number=None):
    """Atomic internal snapshot, strictly sequential, immutable per period.

    No HTTP route exists for this action. Call only from a trusted, separately
    authenticated and independently reconciled back-office process.
    """
    now = timezone.now() if as_of is None else as_of
    account = (PropAccount.objects.select_for_update()
               .select_related("trader").filter(pk=account_id).first())
    if not account or account.kind != PropAccount.Kind.FUNDED:
        raise AllocationRejected("Verified funded account required")
    if account.status != PropAccount.Status.ACTIVE or not account.reference:
        raise AllocationRejected("Funded broker account not active")
    # A single real broker account may never back two separate customer
    # allocations. The broker reference is financial identity, not a label.
    if (account.reference != account.reference.strip()
            or PropAccount.objects.filter(
                kind=PropAccount.Kind.FUNDED, reference=account.reference,
            ).exclude(pk=account.pk).exists()):
        raise AllocationRejected("Broker account reference is not unique")
    if account.policy_version != POLICY.version:
        raise AllocationRejected("Account policy version mismatch")
    if (account.trader.kyc_status != "verified"
            or account.trader.eligibility_status != "eligible"):
        raise AllocationRejected("KYC/eligibility incomplete")
    if not account.reconciled_by_operator:
        raise AllocationRejected("Independent operator reconciliation missing")
    latest_completed = most_recent_completed_period(
        opened_at=account.opened_at, as_of=now
    )
    if latest_completed is None:
        raise AllocationRejected("30-day period has not completed")
    latest = (PropProfitAllocation.objects.filter(account=account)
              .order_by("-period_number").first())
    next_number = 1 if latest is None else latest.period_number + 1
    if period_number is None:
        # An identical request in the same latest period is idempotent;
        # if the treasury missed months, process the oldest one first.
        requested = (
            latest.period_number if latest and latest.period_number == latest_completed.number
            else next_number
        )
    else:
        if (isinstance(period_number, bool) or not isinstance(period_number, int)
                or period_number < 1):
            raise AllocationRejected("Invalid accounting period")
        requested = period_number
    if latest and requested not in (latest.period_number, next_number):
        raise AllocationRejected("Cannot skip or roll back accounting periods")
    if not latest and requested != 1:
        raise AllocationRejected("First allocation must cover first period")
    period = completed_period_by_number(
        opened_at=account.opened_at, as_of=now, period_number=requested
    )
    if period is None:
        raise AllocationRejected("Requested accounting period is not complete")

    executions, marks = _verified_source(account, period_end=period.end)
    projection = account_projection(account, as_of=now, evidence_cutoff=period.end)
    if not projection["verified"] or not projection["risk"].allowed:
        raise AllocationRejected("Historical risk/reconciliation not established")

    # Accept only signed, verified trades from this funded account's opening.
    if any(e.closed_at < account.opened_at for e in executions):
        raise AllocationRejected("Trade before funded-account opening")
    cumulative_net = sum((e.net_realized_usd for e in executions), Decimal("0"))
    source = "\n".join(
        [str(account.id), str(period.number), period.end.isoformat(), str(cumulative_net)]
        + [
            "T|{}|{}|{}|{}|{}|{}|{}".format(
                e.external_event_id, e.evidence_digest, e.data_source,
                e.closed_at.isoformat(), e.symbol,
                e.gross_realized_usd, e.total_fees_usd
            )
            for e in executions
        ]
        + [
            "E|{}|{}|{}|{}|{}".format(
                e.external_event_id, e.evidence_digest,
                e.observed_at.isoformat(), e.equity_usd, e.is_session_open
            )
            for e in marks
        ]
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    existing = PropProfitAllocation.objects.filter(
        account=account, period_number=period.number,
    ).first()
    if existing:
        if existing.evidence_digest != digest or not _journal_is_balanced(existing):
            raise AllocationRejected("Previously staged allocation conflicts with evidence")
        return existing

    allocated_before = sum((
        x.eligible_profit_usd for x in PropProfitAllocation.objects
        .filter(account=account)
    ), Decimal("0"))
    proposal = calculate_payout(
        cumulative_realized_net_profit=cumulative_net,
        previously_allocated_profit=allocated_before,
    )
    allocation = PropProfitAllocation.objects.create(
        account=account, period_number=period.number, start_at=period.start,
        end_at=period.end, cumulative_realized_net_usd=cumulative_net,
        previously_allocated_usd=allocated_before,
        eligible_profit_usd=proposal.eligible_profit_usd,
        trader_profit_usd=proposal.trader_usd,
        company_profit_usd=proposal.company_usd,
        evidence_digest=digest, status="provisional", policy_version=POLICY.version,
    )
    if proposal.eligible_profit_usd > 0:
        entries = [("pool_debit", "debit", proposal.eligible_profit_usd)]
        if proposal.trader_usd > 0:
            entries.append(("trader_credit", "credit", proposal.trader_usd))
        if proposal.company_usd > 0:
            entries.append(("company_credit", "credit", proposal.company_usd))
        PropProfitJournalLine.objects.bulk_create([
            PropProfitJournalLine(allocation=allocation, code=code,
                                  side=side, amount_usd=amount)
            for code, side, amount in entries
        ])
    if not _journal_is_balanced(allocation):
        raise AllocationRejected("Unbalanced provisional profit journal")
    return allocation
