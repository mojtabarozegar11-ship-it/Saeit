"""Bounded aggregate commerce telemetry; events never prove buyer settlement."""
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import CommerceFunnelEvent


@staff_member_required
@require_GET
def commerce_funnel_api(request):
    """Read-only 30-day event counts; no buyer IDs, emails or raw UTM."""
    end = timezone.now()
    start = end - timedelta(days=30)
    rows = CommerceFunnelEvent.objects.filter(
        created_at__gte=start, created_at__lte=end
    )
    names = tuple(event for event, _label in CommerceFunnelEvent.EVENT_CHOICES)
    by_event = {event: 0 for event in names}
    unknown_events = 0
    for item in rows.values("event_name").annotate(n=Count("pk")):
        if item["event_name"] in by_event:
            by_event[item["event_name"]] = item["n"]
        else:
            unknown_events += item["n"]

    # Preselect 25 most-active products; no unbounded per-product N+1 queries.
    ranking = list(
        rows.filter(product_id__isnull=False)
        .values("product_id", "product__title")
        .annotate(n=Count("pk"))
        .order_by("-n", "product_id")[:25]
    )
    selected = [r["product_id"] for r in ranking]
    summaries = {
        r["product_id"]: {
            "product_id": r["product_id"],
            "title": r["product__title"],
            "events": {event: 0 for event in names},
        }
        for r in ranking
    }
    if selected:
        for item in (
            rows.filter(product_id__in=selected)
            .values("product_id", "event_name")
            .annotate(n=Count("pk"))
        ):
            if item["event_name"] in by_event:
                summaries[item["product_id"]]["events"][item["event_name"]] = item["n"]

    response = JsonResponse({
        "schema_version": 2,
        "window_days": 30,
        "window_end": end.isoformat(),
        "read_only": True,
        "events": by_event,
        "unknown_events": unknown_events,
        "products": [summaries[r["product_id"]] for r in ranking],
        "product_limit": 25,
        "products_truncated": len(ranking) == 25,
        "event_count_not_unique_buyers": True,
        "independently_settled_cash": None,
        "independently_verified_delivery": None,
    })
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response
