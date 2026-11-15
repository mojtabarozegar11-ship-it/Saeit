"""Read-only Moj Prop commercial pipeline audit, with no PII or income claims."""
import json

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from core.models import MojPropOffer, MojPropRequest


def pipeline_snapshot():
    """Derive directly from real DB records, never from templates or CI."""
    lead_count = MojPropRequest.objects.count()
    offers = MojPropOffer.objects.all()
    routes = dict(
        MojPropRequest.objects.values_list("route")
        .annotate(n=Count("pk")).order_by("route")
    )
    offer_status = dict(
        offers.values_list("status").annotate(n=Count("pk")).order_by("status")
    )
    unique_quoted_leads = offers.values("lead_id").distinct().count()
    accepted_leads = offers.filter(status="accepted").values("lead_id").distinct().count()
    # This data is not a payment ledger. No sum of quotes is a revenue KPI.
    return {
        "schema": "mojprop.pipeline.v1",
        "as_of_utc": timezone.now().isoformat(),
        "total_inquiries": lead_count,
        "inquiries_by_route": routes,
        "active_new_leads": MojPropRequest.objects.filter(status="new").count(),
        "reviewing_leads": MojPropRequest.objects.filter(status="reviewing").count(),
        "product_specific_inquiries": MojPropRequest.objects.filter(
            route="digital", product_id__isnull=False
        ).count(),
        "distinct_leads_with_quotes": unique_quoted_leads,
        "quotes_by_status": offer_status,
        "distinct_accepted_quotes": accepted_leads,
        "quote_coverage_percent": (
            round(100 * unique_quoted_leads / lead_count, 2) if lead_count else None
        ),
        "acceptance_rate_percent": (
            round(100 * accepted_leads / unique_quoted_leads, 2)
            if unique_quoted_leads else None
        ),
        "payments_independently_verified": None,
        "commercial_delivery_verified": None,
        "collected_revenue": None,
        "scope_note": "Quote acceptance is not payment, delivery, or realized income.",
    }


class Command(BaseCommand):
    help = "Audit real Moj Prop demand and quotation pipeline; never infer revenue."

    def handle(self, *args, **options):
        snapshot = pipeline_snapshot()
        self.stdout.write(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
