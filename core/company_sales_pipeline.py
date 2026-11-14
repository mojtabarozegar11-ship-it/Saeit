"""One-bot sales inquiry KPI, sourced from actual CompanyInquiry CRM rows.

Metrics are not qualified leads, booked sales, collectible receivables,
customer contacts, contracts or verified net profit.
"""
from datetime import timedelta
from django.db.models import Count
from django.utils import timezone

from .company_inquiry_models import CompanyInquiry
from .models import AuditLog

MAX_DAYS = 90


def sales_pipeline_snapshot(*, days=30):
    if type(days) is not int or not 1 <= days <= MAX_DAYS:
        raise ValueError("SALES_WINDOW_INVALID")
    now = timezone.now()
    qs = CompanyInquiry.objects.filter(created_at__gte=now - timedelta(days=days))
    status = dict(qs.values_list("status").annotate(n=Count("id")))
    by_kind = dict(qs.values_list("kind").annotate(n=Count("id")))
    old_new = qs.filter(
        status="new", created_at__lt=now - timedelta(hours=48)
    ).count()
    return {
        "bot_id": "mojtaba.bot.ai",
        "read_only": True,
        "window_days": days,
        "inquiries_received": qs.count(),
        "status_counts": dict(sorted(status.items())),
        "kind_counts": dict(sorted(by_kind.items())),
        "new_older_than_48h_requires_review": old_new,
        "source_of_truth": "core.CompanyInquiry",
        "buyer_contacted": None,
        "lead_qualified": None,
        "quote_accepted": None,
        "settled_cash": None,
        "verified_profit": None,
        "automatic_contact_enabled": False,
        "requires_owner_review": True,
    }
