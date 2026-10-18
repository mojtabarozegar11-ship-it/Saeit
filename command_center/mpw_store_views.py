"""Owner-only, read-only MojPlayWin store readiness; never changes financial state.

The Product/Order tables in the shared Django deployment have no tenant FK.
Consequently global totals are explicitly labelled shared, and MojPlayWin totals
count ONLY products carrying an exact site/tenant marker in JSON metadata.
No saleability or wallet settlement is inferred from these flags.
"""
from django.db import DatabaseError
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.models import Order, PaymentIntent, Product

_ALLOWED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


def _is_mpw_product(metadata):
    return isinstance(metadata, dict) and (
        metadata.get("tenant") == "mojplaywin-main"
        or metadata.get("site") == "mojplaywin.com"
    )


def store_snapshot():
    """Count only observable DB facts, without inspecting payment secrets or PII."""
    counts = {
        "shared_products": 0,
        "shared_active": 0,
        "shared_priced": 0,
        "shared_usd": 0,
        "shared_payment_live_flag": 0,
        "mpw_explicitly_tagged": 0,
        "mpw_active": 0,
        "mpw_priced": 0,
        "mpw_payment_live_flag": 0,
        "mpw_checkout_candidates_unverified": 0,
        "shared_paid_orders": Order.objects.filter(status="paid").count(),
        "shared_orders_total": Order.objects.count(),
        "shared_payment_intents": PaymentIntent.objects.count(),
    }
    for active, price, currency, metadata in Product.objects.values_list(
        "active", "price", "currency", "metadata"
    ).iterator(chunk_size=250):
        counts["shared_products"] += 1
        priced = price is not None and price > 0
        payment_flag = isinstance(metadata, dict) and metadata.get("payment_live") is True
        counts["shared_active"] += int(bool(active))
        counts["shared_priced"] += int(priced)
        counts["shared_usd"] += int(currency == "USD")
        counts["shared_payment_live_flag"] += int(payment_flag)
        if _is_mpw_product(metadata):
            counts["mpw_explicitly_tagged"] += 1
            counts["mpw_active"] += int(bool(active))
            counts["mpw_priced"] += int(priced)
            counts["mpw_payment_live_flag"] += int(payment_flag)
            counts["mpw_checkout_candidates_unverified"] += int(
                bool(active) and priced and currency == "USD" and payment_flag
            )
    counts["products_without_explicit_mpw_scope"] = (
        counts["shared_products"] - counts["mpw_explicitly_tagged"]
    )
    return {
        "tenant": "mojplaywin-main",
        "source": "live_shared_django_database",
        "read_only": True,
        "checkout_confirmed": False,
        "notes": [
            "Shared totals can include other hostnames; do not claim they belong to MojPlayWin.",
            "A payment_live metadata flag does not establish delivery, wallet coverage, or a successful payment.",
            "No purchase, product activation, invoice, payment, or publication occurs here.",
        ],
        "counts": counts,
    }


def _check(request):
    if request.get_host().split(":")[0].lower() not in _ALLOWED_HOSTS:
        raise Http404("Not a MojPlayWin host")
    if not request.user.is_authenticated or not request.user.is_superuser:
        return HttpResponseForbidden("Owner-only store readiness")
    return None


def _headers(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_GET
def dashboard(request):
    denied = _check(request)
    if denied is not None:
        return denied
    try:
        data = store_snapshot()
    except DatabaseError:
        return _headers(JsonResponse({"status": "unavailable", "reason": "database_error"}, status=503))
    return _headers(render(request, "command_center/mpw_store_control.html", data))


@require_GET
def overview_api(request):
    denied = _check(request)
    if denied is not None:
        return denied
    try:
        data = store_snapshot()
    except DatabaseError:
        return _headers(JsonResponse({"status": "unavailable", "reason": "database_error"}, status=503))
    return _headers(JsonResponse(data))
