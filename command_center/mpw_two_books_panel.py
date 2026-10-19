"""Main-MojPlayWin-only read-only reality dashboard for 2 owned books.

No wallet addresses, private paths, user PII, checkout switches or side effects.
Unknown providers/delivery are UNKNOWN rather than green/success.
"""
from django.apps import apps
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.models import Order, OrderItem, PaymentIntent, Product
from .mpw_public import is_main

BOOK_IDS = (72, 225)
FLAGS = (
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
    "MPW_COMMERCE_INVOICING_ENABLED",
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
)
PRODUCT_FLAGS = (
    "quality_approved", "license_verified", "factory_publication_permission",
    "asset_verified", "checkout_enabled", "payment_live",
)
BOOK_LABELS = {
    72: "The Science and Practice of Chess Improvement",
    225: "Taniya and the Little Baker Worms",
}


def _status_dict():
    active_flags = {name: getattr(settings, name, None) is True for name in FLAGS}
    found = {p.pk: p for p in Product.objects.filter(pk__in=BOOK_IDS).select_related("knowledge_article")}
    books = []
    for pk in BOOK_IDS:
        obj = found.get(pk)
        if obj is None:
            books.append({"id": pk, "name": BOOK_LABELS[pk], "exists": False,
                          "sale_ready": False, "buyer_orders": 0,
                          "paid_orders": 0, "verified_downloads": None})
            continue
        meta = obj.metadata if isinstance(obj.metadata, dict) else {}
        permissions = {name: meta.get(name) is True for name in PRODUCT_FLAGS}
        # Metadata's file presence is NOT proof of entitlement-based delivery.
        purchases = OrderItem.objects.filter(product_id=pk)
        payment_orders = purchases.filter(order__status="paid")
        ready = bool(
            obj.active and obj.owner_id and obj.knowledge_article_id
            and obj.knowledge_article.published and all(active_flags.values())
            and all(permissions.values())
        )
        books.append({
            "id": pk,
            "name": obj.title,
            "exists": True,
            "price": str(obj.price),
            "currency": obj.currency,
            "active": obj.active,
            "has_recorded_owner": bool(obj.owner_id),
            "knowledge_published": bool(obj.knowledge_article_id and obj.knowledge_article.published),
            "permissions": permissions,
            "sale_ready": ready,
            "buyer_orders": purchases.values("order_id").distinct().count(),
            "paid_orders": payment_orders.values("order_id").distinct().count(),
            "verified_downloads": None,  # Must come from verified receipts, not assumptions.
        })

    order_ids = OrderItem.objects.filter(product_id__in=BOOK_IDS).values("order_id")
    orders = Order.objects.filter(pk__in=order_ids)
    intents = PaymentIntent.objects.filter(order__in=orders)
    by_status = {}
    for code in orders.values_list("status", flat=True):
        by_status[code] = by_status.get(code, 0) + 1
    intent_status = {}
    for code in intents.values_list("status", flat=True):
        intent_status[code] = intent_status.get(code, 0) + 1

    # Two different payment engines have existed on the live host.
    # Do not infer invoices from the core.Order count or guess their DB schema.
    native_invoices = None
    try:
        invoice_model = apps.get_model("mpw_native_checkout", "NativeInvoice")
        native_invoices = invoice_model.objects.count()
    except LookupError:
        pass
    return {
        "books": books,
        "flags": active_flags,
        "all_gateway_flags_enabled": all(active_flags.values()),
        "orders_total": orders.count(),
        "orders_by_status": by_status,
        "intents_total": intents.count(),
        "intents_by_status": intent_status,
        "native_invoices_count": native_invoices,
        "verified_customer_downloads": None,
        "real_settlement_test_verified": False,  # Never claim real settlement from flags.
        "can_enable_payments": False,  # Operational release requires externally audited evidence.
        "mode": "read_only_observability_not_a_payment_switch",
    }


@staff_member_required
@require_GET
def dashboard(request):
    if not is_main(request):
        raise Http404("This information is restricted to MojPlayWin main domain.")
    response = render(request, "command_center/mpw_two_books_panel.html", _status_dict())
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
