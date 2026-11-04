from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum
from .models import Account, JournalEntry


def _money(value):
    return str((value or Decimal("0")).quantize(Decimal("0.01")))


def _is_balanced(entry):
    try:
        entry.validate_balanced()
    except ValidationError:
        return False
    return True


def ledger_summary(limit=12):
    balances = []
    for account in Account.objects.filter(is_active=True).order_by("code"):
        totals = account.journal_lines.filter(entry__status=JournalEntry.Status.POSTED).aggregate(
            debit=Sum("debit"), credit=Sum("credit")
        )
        debit = totals["debit"] or Decimal("0")
        credit = totals["credit"] or Decimal("0")
        balances.append({
            "code": account.code, "name": account.name, "kind": account.kind,
            "debit": _money(debit), "credit": _money(credit),
            "balance": _money(debit - credit),
        })
    entries = []
    for entry in JournalEntry.objects.filter(status=JournalEntry.Status.POSTED).prefetch_related("lines__account")[:limit]:
        total = sum((line.debit for line in entry.lines.all()), Decimal("0"))
        entries.append({
            "reference": entry.reference, "date": entry.occurred_on.isoformat(),
            "memo": entry.memo, "total": _money(total),
        })
    posted = JournalEntry.objects.filter(status=JournalEntry.Status.POSTED).prefetch_related("lines")
    return {
        "accounts": balances,
        "recent_entries": entries,
        "posted_entries": posted.count(),
        "draft_entries": JournalEntry.objects.filter(status=JournalEntry.Status.DRAFT).count(),
        "integrity": {
            "balanced_posted_entries": all(_is_balanced(entry) for entry in posted),
            "source": "Django double-entry ledger",
        },
    }
