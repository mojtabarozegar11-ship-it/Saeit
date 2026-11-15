"""Read-only commercial conversion desk; aggregate only, never reveal buyer PII.

Counts genuine canonical MojPropRequest submissions and states. No order,
funding, email or payment is created. Intended for an authorized operator
terminal; output has NO customer identifiers.
"""
from datetime import timedelta
import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone
from core.models import MojPropRequest


class Command(BaseCommand):
    help = "Report real (non-paid) Moj Prop inquiry funnel counts, without PII."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        days=options["days"]
        if type(days) is not int or not 1<=days<=90:
            raise CommandError("days_must_be_between_1_and_90")
        since=timezone.now()-timedelta(days=days)
        qs=MojPropRequest.objects.filter(created_at__gte=since)
        by_status=dict(qs.values_list("status").annotate(count=Count("id")))
        by_route=dict(qs.values_list("route").annotate(count=Count("id")))
        total=qs.count()
        created=qs.filter(status="new").count()
        reviewing=qs.filter(status="reviewing").count()
        # Inquiries waiting for first review > 24h need attention.
        overdue=qs.filter(status="new", reviewed_at__isnull=True,
                          created_at__lt=timezone.now()-timedelta(hours=24)).count()
        data={
            "window_days":days,
            "manual_requests_received":total,
            "new_unreviewed":created,
            "under_review":reviewing,
            "past_24h_review_sla":overdue,
            "by_status":by_status,
            "by_route":by_route,
            # A request, a written offer and delivered service are not proof
            # that money settled on-chain or a bank statement reconciled.
            "confirmed_paid_revenue_usd":None,
            "settlement_evidence_checked":False,
            "customer_data_included":False,
        }
        if options["json"]:
            self.stdout.write(json.dumps(data,sort_keys=True))
        else:
            self.stdout.write(
                f"window_days={days} inquiries={total} new={created} "
                f"under_review={reviewing} overdue_24h={overdue} "
                "paid_revenue=NOT_VERIFIED"
            )
