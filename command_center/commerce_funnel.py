from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone

from core.models import CommerceFunnelEvent


# Server-side events describe backend observations, not proof of a human visitor.
# In particular, begin_checkout is created by a checkout GET and can include
# crawlers, uptime checks and internal verification requests.
EVENT_SEMANTICS = {
    "view_store": {
        "classification": "request_level",
        "human_evidence": False,
        "sale_evidence": False,
        "note": "Backend request; do not treat as a unique human visit.",
    },
    "view_item": {
        "classification": "request_level",
        "human_evidence": False,
        "sale_evidence": False,
        "note": "Backend request; do not treat as a unique human visit.",
    },
    "begin_checkout": {
        "classification": "request_level",
        "human_evidence": False,
        "sale_evidence": False,
        "note": "Checkout GET; may include bots, monitoring and internal verification.",
    },
    "invoice_created": {
        "classification": "server_business_event",
        "human_evidence": False,
        "sale_evidence": False,
        "note": "Invoice issuance only; no payment or revenue claim.",
    },
    "payment_confirmed": {
        "classification": "server_business_event",
        "human_evidence": False,
        "sale_evidence": "payment_event_only",
        "note": "Correlate with the authoritative payment and settlement ledger.",
    },
    "delivery_success": {
        "classification": "server_business_event",
        "human_evidence": False,
        "sale_evidence": "delivery_event_only",
        "note": "Delivery event only; do not infer a unique human from it.",
    },
    "delivery_failure": {
        "classification": "server_business_event",
        "human_evidence": False,
        "sale_evidence": False,
        "note": "Delivery failure event only.",
    },
}


@staff_member_required
def commerce_funnel_api(request):
    """Read-only funnel summary for staff; never exposes visitor identifiers."""
    since = timezone.now() - timedelta(days=30)
    rows = CommerceFunnelEvent.objects.filter(created_at__gte=since)
    by_event = {
        event: rows.filter(event_name=event).count()
        for event, _label in CommerceFunnelEvent.EVENT_CHOICES
    }
    products = []
    for product_id in rows.filter(product_id__isnull=False).values_list("product_id", flat=True).distinct():
        product_rows = rows.filter(product_id=product_id)
        product = product_rows.select_related("product").first().product
        products.append({
            "product_id": product_id,
            "title": product.title,
            "events": {
                event: product_rows.filter(event_name=event).count()
                for event, _label in CommerceFunnelEvent.EVENT_CHOICES
            },
        })
    return JsonResponse({
        "window_days": 30,
        "read_only": True,
        "events": by_event,
        "event_semantics": EVENT_SEMANTICS,
        "products": products,
    })
