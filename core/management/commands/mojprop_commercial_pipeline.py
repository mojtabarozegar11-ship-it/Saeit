"""Read-only Moj Prop commercial pipeline audit, with no PII or income claims."""
import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from core.models import MojPropOffer, MojPropRequest, MojPropDeliveryEvidence


def pipeline_snapshot():
    """Derive directly from real DB records, never from templates or CI."""
    now = timezone.now()
    lead_count = MojPropRequest.objects.count()
    offers = MojPropOffer.objects.all()
    routes = dict(
        MojPropRequest.objects.values_list("route")
        .annotate(n=Count("pk")).order_by("route")
    )
    offer_status = dict(
        offers.values_list("status").annotate(n=Count("pk")).order_by("status")
    )
    # An unissued draft is NOT a quote delivered to a potential buyer.
    unique_draft_or_quoted = offers.values("lead_id").distinct().count()
    # A timestamp alone on a draft is not evidence that an offer was issued.
    issued = offers.filter(
        status__in=("issued", "accepted", "cancelled", "expired"),
        reviewed_at__isnull=False, issued_at__isnull=False,
    )
    unique_issued_leads = issued.values("lead_id").distinct().count()
    # Ignore inconsistent rows created outside model.full_clean/admin review.
    accepted = issued.filter(status="accepted", accepted_at__isnull=False).exclude(
        acceptance_reference=""
    )
    accepted_leads = accepted.values("lead_id").distinct().count()
    handoffs = MojPropDeliveryEvidence.objects.all()
    handed_off = handoffs.filter(
        status__in=("sent", "acknowledged"), handed_off_at__isnull=False,
        offer_id__in=accepted.values("pk"),
        clearance_reference__gt="", handoff_reference__gt="",
    )
    acknowledged = handed_off.filter(
        status="acknowledged", acknowledged_at__isnull=False,
        acknowledgment_reference__gt="",
    )
    unquoted = MojPropRequest.objects.exclude(pk__in=issued.values("lead_id"))
    stale_threshold = now - timedelta(hours=24)
    # This data is not a payment ledger. No sum of quotes is a revenue KPI.
    return {
        "schema": "mojprop.pipeline.v1",
        "as_of_utc": now.isoformat(),
        "total_inquiries": lead_count,
        "inquiries_by_route": routes,
        "active_new_leads": MojPropRequest.objects.filter(status="new").count(),
        "reviewing_leads": MojPropRequest.objects.filter(status="reviewing").count(),
        "product_specific_inquiries": MojPropRequest.objects.filter(
            route="digital", product_id__isnull=False
        ).count(),
        "distinct_leads_with_quotes": unique_draft_or_quoted,
        "distinct_leads_with_issued_quotes": unique_issued_leads,
        "distinct_accepted_leads": accepted_leads,
        "quotes_by_status": offer_status,
        "distinct_accepted_quotes": accepted.count(),
        "private_artifacts_prepared": handoffs.filter(status="prepared").count(),
        "handoffs_recorded": handed_off.count(),
        "customer_acknowledgments_recorded": acknowledged.count(),
        "handoff_coverage_percent": (
            round(100 * handed_off.count() / accepted.count(), 2)
            if accepted.exists() else None
        ),
        "drafts_not_issued": offers.filter(status="draft", issued_at__isnull=True).count(),
        "new_leads_without_issued_quote": unquoted.filter(status="new").count(),
        "new_unquoted_leads_older_than_24h": unquoted.filter(
            status="new", created_at__lt=stale_threshold
        ).count(),
        "issued_quotes_expired_without_acceptance": offers.filter(
            status="issued", expires_at__lte=now
        ).count(),
        "issued_quotes_awaiting_decision": offers.filter(
            status="issued", expires_at__gt=now
        ).count(),
        "quote_draft_coverage_percent": (
            round(100 * unique_draft_or_quoted / lead_count, 2) if lead_count else None
        ),
        "quote_coverage_percent": (
            round(100 * unique_issued_leads / lead_count, 2) if lead_count else None
        ),
        "acceptance_rate_percent": (
            round(100 * accepted_leads / unique_issued_leads, 2)
            if unique_issued_leads else None
        ),
        "payments_independently_verified": None,
        "commercial_delivery_verified": None,
        "collected_revenue": None,
        "scope_note": "Drafts, issued quotes, accepted terms, handoff records and independent payment are separate evidence stages.",
    }


class Command(BaseCommand):
    help = "Audit real Moj Prop demand and quotation pipeline; never infer revenue."

    def handle(self, *args, **options):
        snapshot = pipeline_snapshot()
        self.stdout.write(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
