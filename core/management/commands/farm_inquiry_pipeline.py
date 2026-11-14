"""Read-only aggregated funnel evidence for the existing Zomorod CRM.

Never prints customer identity, email, phone, message, records or pricing.
This is not a revenue receipt or a settlement checker.
"""
import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from core.company_inquiry_models import CompanyInquiry

_STATES = ("new", "reviewing", "approved", "closed")


class Command(BaseCommand):
    help = "Read-only farm economics requests by CRM stage; no customer PII"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        days = options["days"]
        if type(days) is not int or not 1 <= days <= 366:
            raise ValueError("days must be an integer in 1..366")
        cutoff = timezone.now() - timedelta(days=days)
        rows = CompanyInquiry.objects.filter(
            kind="commercial",
            subject__startswith="ZM-FARM",
            created_at__gte=cutoff,
        ).values("status").annotate(count=Count("id")).order_by("status")
        counts = {state: 0 for state in _STATES}
        unknown_status = 0
        for row in rows:
            if row["status"] in counts:
                counts[row["status"]] += row["count"]
            else:
                unknown_status += row["count"]
        result = {
            "schema": "zomorod.farm.inquiry-pipeline.v1",
            "source": "CompanyInquiry persisted CRM",
            "days": days,
            "matched_inquiries": sum(counts.values()) + unknown_status,
            "status_counts": counts,
            "unknown_status_count": unknown_status,
            "observed_at": timezone.now().isoformat(timespec="seconds"),
            "data_source": "configured Django CompanyInquiry database",
            "financial_certification": False,
            "confirmed_customer_contracts": None,
            "confirmed_collected_revenue": None,
            "delivered_paid_reports": None,
            "pii_exposed": False,
        }
        self.stdout.write("ZM_FARM_PIPELINE=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
