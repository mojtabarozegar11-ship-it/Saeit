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


def private_response(data, *, status):
    response = JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "private, no-store, no-cache, max-age=0, must-revalidate"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Content-Type-Options"] = "nosniff"
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
