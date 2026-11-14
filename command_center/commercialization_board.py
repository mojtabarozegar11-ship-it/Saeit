"""Private read-only commercialization control board.

No customer PII, wallet addresses, invoice IDs, prices, or payout actions.
Shared Django commerce models may not reflect the separate TRX production
runtime; therefore a database status is *never* reported as proven revenue.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.commercialization_readiness import build_board
from core.models import (
    CommerceFunnelEvent, Product, Order, PaymentIntent,
    LedgerEntry, PaymentWebhookEvent,
)
from core.mojplaywin_product_detail import PUBLIC_CATALOG
from core.signal_commercial_catalog import catalog as signal_catalog
from core.tron_rollout_inventory import inspect_rollout
from prop_firm.plans import CHALLENGE_PLANS


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
        row["id"]: row
        for row in Product.objects.filter(pk__in=PUBLIC_CATALOG, active=True)
        .values("id", "title", "price", "currency")
    }
    matches = sorted(
        sku for sku, info in PUBLIC_CATALOG.items()
        if listed.get(sku, {}).get("title") == info["title"]
    )
    price_matches = sorted(
        sku for sku in matches
        if listed[sku]["currency"] == "USD"
        and listed[sku]["price"] == Decimal(PUBLIC_CATALOG[sku]["expected_price_usd"])
    )

    data = build_board()  # no invented operator attestations
    data["observed"] = {
        "source": "shared_django_models_not_external_trx_settlement",
        "catalog_cards_declared": len(PUBLIC_CATALOG),
        "catalog_products_active_title_matched": len(matches),
        "catalog_matched_ids": matches,
        "catalog_products_active_price_matched": len(price_matches),
        "catalog_price_verified_listing_ids": price_matches,
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
    signal_rows = signal_catalog()
    rollout = inspect_rollout()
    data["financial_commerce"] = {
        "moj_prop": {
            "plan_products_configured": len(CHALLENGE_PLANS),
            "plan_one_owner_fee_trx": str(CHALLENGE_PLANS[0].entry_fee_trx),
            "additional_plan_prices_proposed_not_live": 9,
            "same_policy_all_plans": True,
            "valid_closed_trades_required": CHALLENGE_PLANS[0].minimum_verified_closed_trades,
            "duration_days": CHALLENGE_PLANS[0].duration_days,
            "live_challenge_checkout_verified": False,
            "real_broker_funding_verified": False,
        },
        "signals": {
            "known_financial_brands": len({row.brand for row in signal_rows}),
            "localization_contexts": len(signal_rows),
            "live_subscriptions_verified": sum(
                row.checkout_enabled is True for row in signal_rows
            ),
            "canonical_bot": "mojtaba.bot.ai",
        },
        "tron": {
            "grounded_site_domains": rollout["known_canonical_site_domains"],
            "isolated_logical_scopes": rollout["logical_payment_scopes_not_hosts"],
            "invoice_created_by_this_api": False,
            "live_gateway_verified_by_this_api": False,
        },
        "owner_priority_order": [
            "moj_prop", "signal_subscriptions", "tron_gateway", "mojplaywin_store",
        ],
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



@staff_member_required
@require_GET
def commercialization_board_page(request):
    """Private bilingual control surface; decisions are not payment actions."""
    board = build_board()  # No auto-attested readiness.
    response = render(request, "command_center/commercialization_board.html", {
        "sectors": board["sectors"],
        "eligible": board["eligible_for_commercial_review"],
    })
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
