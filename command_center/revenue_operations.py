"""Owner-only operational revenue/lead evidence, for the single mojtaba.bot.ai.

One real database read path. Does not create leads, trigger mail, touch payment,
expose contact PII, or infer settled revenue from internal status/telemetry.
"""
from datetime import timedelta

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import CompanyInquiry, CommerceFunnelEvent

WINDOWS = frozenset({7, 30, 90})
STATES = ("new", "reviewing", "approved", "closed")
KINDS = tuple(x[0] for x in CompanyInquiry.KIND_CHOICES)
EVENTS = tuple(x[0] for x in CommerceFunnelEvent.EVENT_CHOICES)


def build_operations_snapshot(*, days=30, now=None):
    """Snapshot of facts; never convert inquiry 'approved' or payment event to cash."""
    if type(days) is not int or days not in WINDOWS:
        raise ValueError("days must be 7, 30 or 90")
    end = now or timezone.now()
    start = end - timedelta(days=days)
    inquiries = CompanyInquiry.objects.filter(
        created_at__gte=start, created_at__lte=end
    )
    by_status = {name: 0 for name in STATES}
    unknown_status = 0
    for item in inquiries.values("status").annotate(n=Count("pk")):
        if item["status"] in by_status:
            by_status[item["status"]] = item["n"]
        else:
            unknown_status += item["n"]
    by_kind = {name: 0 for name in KINDS}
    unknown_kind = 0
    for item in inquiries.values("kind").annotate(n=Count("pk")):
        if item["kind"] in by_kind:
            by_kind[item["kind"]] = item["n"]
        else:
            unknown_kind += item["n"]

    backlog = CompanyInquiry.objects.exclude(status="closed").filter(
        created_at__lte=end
    )
    backlog_size = backlog.count()
    oldest = backlog.order_by("created_at").values_list("created_at", flat=True).first()
    oldest_age = max(0, (end - oldest).days) if oldest is not None else None

    events = {name: 0 for name in EVENTS}
    unattributed_events = 0
    funnel = CommerceFunnelEvent.objects.filter(
        created_at__gte=start, created_at__lte=end
    )
    for item in funnel.values("event_name").annotate(n=Count("pk")):
        if item["event_name"] in events:
            events[item["event_name"]] = item["n"]
        else:
            unattributed_events += item["n"]
    # No buyer ID or shared order key exists in these event records.
    # Event counts are not unique customers, not completed sales.
    return {
        "agent": "mojtaba.bot.ai",
        "schema_version": 1,
        "window_days": days,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "read_only": True,
        "privacy": "aggregate_counts_only_no_customer_identifiers",
        "inquiries": {
            "all_in_window": sum(by_status.values()) + unknown_status,
            "statuses": by_status,
            "unknown_status": unknown_status,
            "kinds": by_kind,
            "unknown_kind": unknown_kind,
            "open_backlog_all_time": backlog_size,
            "oldest_open_age_days": oldest_age,
            "approved_means": "preliminary_review_only_not_contract_or_payment",
        },
        "funnel": {
            "event_counts": events,
            "unknown_events": unattributed_events,
            "counting_unit": "events_not_unique_buyers",
            "payment_confirmed_event": "internal_telemetry_not_independent_settlement",
            "delivery_success_event": "internal_telemetry_not_external_delivery_receipt",
        },
        "commercial_evidence": {
            "qualified_unique_leads": None,
            "signed_contracts": None,
            "externally_settled_cash": None,
            "verified_delivered_orders": None,
            "verified_net_profit": None,
        },
        "release_gate": "NO_LIVE_FINANCIAL_CLAIM_FROM_INTERNAL_EVENTS",
    }


@user_passes_test(lambda u: bool(u.is_active and u.is_superuser),
                  login_url="/admin/login/")
@require_GET
def revenue_operations_api(request):
    """Private GET JSON with explicit 400 on unsupported time windows."""
    raw = request.GET.get("days", "30")
    if raw not in ("7", "30", "90"):
        response = JsonResponse(
            {"error": "supported days are 7, 30, 90"}, status=400
        )
    else:
        response = JsonResponse(build_operations_snapshot(days=int(raw)))
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response
