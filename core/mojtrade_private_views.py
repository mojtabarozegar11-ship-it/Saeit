"""Strict owner-only, read-only view of the canonical MojTrade watch feed.

No broker operations, scheduler, trading, email, SMS, payment or public signal
publication. This endpoint never upgrades a watch classification to an order.
"""
from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.utils.cache import patch_vary_headers

from core.chat_operation_security import is_authorized_chat_operator
from core.management.commands.mojtrade_market_watch_export import fresh_canonical_drafts
from core.mojtrade_signal_drafts import MarketWatchDraftError
from core.mojtrade_readiness import trading_readiness_report
from core.financial_brand_pages import BRANDS


def private_response(data, *, status):
    response = JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "private, no-store, no-cache, max-age=0, must-revalidate"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    patch_vary_headers(response, ["Cookie"])
    return response


@never_cache
@require_GET
def owner_private_market_watch(request):
    """Only an authenticated active superuser receives non-executable signals.

    Do not re-use generic staff-read permissions: staff employees must not see
    market-watch research until the owner explicitly authorizes publication.
    """
    if not is_authorized_chat_operator(request.user):
        return private_response({"detail": "owner_access_required"}, status=403)

    try:
        task_id, watch = fresh_canonical_drafts()
    except (MarketWatchDraftError, ValueError, TypeError, DatabaseError):
        # A stale, missing or tampered receipt is never silently replaced by
        # an earlier task or cached content. Return no private signal data.
        return private_response({
            "status": "unavailable",
            "detail": "no_fresh_verified_canonical_market_watch",
            "publication_authorized": False,
            "trade_execution_authorized": False,
        }, status=503)

    return private_response({
        "task_id": task_id,
        "owner": "mojtaba-bot-ai",
        "private_research_only": True,
        "watch": watch,
    }, status=200)



@never_cache
@require_GET
def owner_private_mojtrade_readiness(request):
    """Expose bounded operational proof gates to an active superuser only."""
    if not is_authorized_chat_operator(request.user):
        return private_response({"detail": "owner_access_required"}, status=403)
    try:
        report = trading_readiness_report()
    except DatabaseError:
        return private_response({
            "status": "unavailable",
            "detail": "trading_readiness_database_unavailable",
            "operational_completion_percent": None,
        }, status=503)
    return private_response(report, status=200)



@never_cache
@require_GET
def owner_private_mojtrade_brand_preview(request, brand, locale):
    """Review one of 17 finance brands in FA/EN/AR without public delivery.

    The canonical watch receipt is freshly verified on every request. No
    subscriber entitlement, billing, site publication or order is created.
    """
    if not is_authorized_chat_operator(request.user):
        return private_response({"detail": "owner_access_required"}, status=403)

    name = next((item for item in BRANDS if item[0] == brand), None)
    if name is None or locale not in ("fa", "en", "ar"):
        return private_response({"detail": "unknown_private_preview_scope"}, status=404)

    try:
        task_id, watch = fresh_canonical_drafts()
    except (MarketWatchDraftError, ValueError, TypeError, DatabaseError):
        return private_response({
            "status": "unavailable",
            "detail": "no_fresh_verified_canonical_market_watch",
            "publication_authorized": False,
            "trade_execution_authorized": False,
        }, status=503)

    brand_index = {"fa": 1, "en": 2, "ar": 3}[locale]
    cards = [{
        "symbol": entry["symbol"],
        "classification": entry["classification"],
        "source_provider": entry["source_provider"],
        "source_observed_at": entry["observed_at"],
        "source_signal_id": entry["source_signal_id"],
        "market_watch_text": entry["content"][locale],
        "entry_price": None,
        "stop_loss": None,
        "take_profit": None,
        "order_intent": None,
    } for entry in watch["alerts"]]

    return private_response({
        "schema": "mojtaba.bot.ai.private-brand-watch-preview-v1",
        "canonical_owner": "mojtaba-bot-ai",
        "status": "private_owner_preview_only",
        "brand": brand,
        "brand_name": name[brand_index],
        "locale": locale,
        "task_id": task_id,
        "source_sha256": watch["source_sha256"],
        "draft_sha256": watch["draft_sha256"],
        "expires_at": watch["expires_at"],
        "alerts": cards,
        "publication_authorized": False,
        "external_delivery_receipts": [],
        "broker_connected": False,
        "trade_execution_authorized": False,
        "orders": 0,
        "revenue_verified": False,
    }, status=200)
