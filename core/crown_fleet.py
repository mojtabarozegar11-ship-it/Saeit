"""Read-only Crown cosmetic catalogue and account purchase restoration.

A browser save, a submitted TxID, and an unpaid order never grant a paid jet.
Native settlement remains the sole writer. No schema migration is required.
"""
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import LedgerEntry, OrderItem, Product

SKUS = ("cd-spectre", "cd-valkyrie", "cd-tempest", "cd-phoenix", "cd-sovereign")


def owned_skus(user):
    if not user.is_authenticated:
        return []
    owned = set()
    items = OrderItem.objects.filter(
        order__customer=user, order__status="paid",
        order__payment_intent__status="succeeded",
        product__product_type="game_cosmetic", quantity=1,
    ).select_related("order__payment_intent", "product")
    for item in items:
        sku = (item.product.metadata or {}).get("crown_sku")
        if sku not in SKUS:
            continue
        order = item.order
        intent = order.payment_intent
        if (order.total <= 0 or intent.amount != order.total
                or order.currency != "USD" or intent.currency != order.currency
                or item.currency != order.currency or item.unit_price <= 0
                or not intent.provider_reference or intent.provider in ("", "not_configured", "demo")):
            continue
        ledger = LedgerEntry.objects.filter(order=order)
        if ledger.filter(entry_type__in=("refund", "reversal", "chargeback")).exists():
            continue
        paid = ledger.filter(
            payment_intent=intent, entry_type="payment", currency=order.currency,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        item_total = sum((x.line_total for x in order.items.all()), Decimal("0"))
        if paid == order.total == item_total:
            owned.add(sku)
    return sorted(owned)


def catalogue():
    products = {}
    duplicates = set()
    for p in Product.objects.filter(active=True, product_type="game_cosmetic"):
        md = p.metadata if isinstance(p.metadata, dict) else {}
        sku = md.get("crown_sku")
        if sku not in SKUS:
            continue
        if sku in products:
            duplicates.add(sku)
        products[sku] = p
    items = []
    for sku in SKUS:
        p = products.get(sku)
        md = p.metadata if p else {}
        available = bool(
            getattr(settings, "CROWN_STORE_ENABLED", False) is True
            and p and sku not in duplicates and p.currency == "USD" and p.price >= Decimal("4.00")
            and md.get("crown_checkout_verified") is True
            and md.get("rights_cleared") is True
        )
        items.append({
            "sku": sku, "price": format(p.price, ".2f") if p else "0.00",
            "currency": "USD", "available": available,
            "checkout": f"/store/product/{p.pk}/checkout/" if available else None,
        })
    return items


@never_cache
@require_GET
def fleet(request):
    if request.get_host().split(":")[0].lower() not in ("mojplaywin.com", "www.mojplaywin.com"):
        raise Http404
    response = JsonResponse({
        "game": "crown-defender", "version": 1,
        "authenticated": request.user.is_authenticated,
        "items": catalogue(), "owned": owned_skus(request.user),
    })
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Cookie"
    response["X-Content-Type-Options"] = "nosniff"
    return response
