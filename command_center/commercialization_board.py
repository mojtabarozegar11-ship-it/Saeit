"""Private read-only commercialization control board.

No customer PII, wallet addresses, invoice IDs, prices, or payout actions.
Shared Django commerce models may not reflect the separate TRX production
runtime; therefore a database status is *never* reported as proven revenue.
"""
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.commercialization_readiness import build_board
from core.models import (
    CommerceFunnelEvent, Product, Order, PaymentIntent,
    LedgerEntry, PaymentWebhookEvent,
)
from core.mojplaywin_product_detail import PUBLIC_CATALOG


@staff_member_required
@require_GET
def commercialization_board_api(request):
    """Staff-only observational facts plus strict, unverified release gates."""
    since = timezone.now() - timedelta(days=30)
    rows = CommerceFunnelEvent.objects.filter(created_at__gte=since)
    by_event = {
        row["event_name"]: row["total"]
        for row in rows.values("event_name").annotate(total=Count("pk"))
    }
    # These counts show events, not unique buyers, paid orders, or cash revenue.
    listed = {
        row["id"]: row["title"]
        for row in Product.objects.filter(pk__in=PUBLIC_CATALOG, active=True)
        .values("id", "title")
    }
    matches = sorted(
        sku for sku, info in PUBLIC_CATALOG.items()
        if listed.get(sku) == info["title"]
    )

    data = build_board()  # no invented operator attestations
    data["observed"] = {
        "source": "shared_django_models_not_external_trx_settlement",
        "catalog_cards_declared": len(PUBLIC_CATALOG),
        "catalog_products_active_title_matched": len(matches),
        "catalog_matched_ids": matches,
        "shared_database": {
            "active_products_all_brands": Product.objects.filter(active=True).count(),
            "orders_all_brands": Order.objects.count(),
            "payment_intents_all_brands": PaymentIntent.objects.count(),
            "provider_selected_intents_all_brands": PaymentIntent.objects.exclude(
                provider="not_configured").count(),
            "internal_ledger_entries_all_brands": LedgerEntry.objects.count(),
            "webhook_events_all_brands": PaymentWebhookEvent.objects.count(),
        },
        "funnel_events_last_30_days_all_brands": {
            name: by_event.get(name, 0) for name, _ in CommerceFunnelEvent.EVENT_CHOICES
        },
        "funnel_window_days": 30,
    }
    data["warnings"] = [
        "An intent, webhook, or analytics event is not independently reconciled cash.",
        "The external MojPlayWin TRX runtime may not be represented in this Django database.",
        "Do not accept payments until pricing, rights, confirmed chain settlement and delivery are verified.",
    ]
    response = JsonResponse(data)
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Content-Type-Options"] = "nosniff"
    return response
