from decimal import Decimal
from django.db.models import Count, F, Q, Sum
from .models import Account, JournalEntry


def _money(value):
    return str((value or Decimal("0")).quantize(Decimal("0.01")))


def ledger_summary(limit=12):
    """Constant-query read-only summary, even with many posted journal lines."""
    balances = []
    posted_lines = Q(journal_lines__entry__status=JournalEntry.Status.POSTED)
    accounts = Account.objects.annotate(
        posted_debit=Sum("journal_lines__debit", filter=posted_lines),
        posted_credit=Sum("journal_lines__credit", filter=posted_lines),
        posted_line_count=Count("journal_lines", filter=posted_lines),
    ).order_by("code")
    for account in accounts:
        if not account.is_active and not account.posted_line_count:
            continue
        debit = account.posted_debit or Decimal("0")
        credit = account.posted_credit or Decimal("0")
        balances.append({
            "code": account.code, "name": account.name, "kind": account.kind,
            "debit": _money(debit), "credit": _money(credit),
            "balance": _money(debit - credit),
        })
    entries = [
        {
            "reference": entry.reference, "date": entry.occurred_on.isoformat(),
            "memo": entry.memo, "total": _money(entry.total_debit),
        }
        for entry in JournalEntry.objects.filter(status=JournalEntry.Status.POSTED)
        .annotate(total_debit=Sum("lines__debit"))[:limit]
    ]
    counts = dict(JournalEntry.objects.values_list("status").annotate(count=Count("pk")))
    invalid_posted = (JournalEntry.objects.filter(status=JournalEntry.Status.POSTED)
                      .annotate(total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit"))
                      .filter(Q(total_debit__isnull=True) | Q(total_debit__lte=0) |
                              ~Q(total_debit=F("total_credit"))).exists())
    return {
        "accounts": balances,
        "recent_entries": entries,
        "posted_entries": counts.get(JournalEntry.Status.POSTED, 0),
        "draft_entries": counts.get(JournalEntry.Status.DRAFT, 0),
        "integrity": {
            "balanced_posted_entries": not invalid_posted,
            "source": "Django double-entry ledger",
        },
    }
