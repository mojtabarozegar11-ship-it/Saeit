"""Main-MojPlayWin-only read-only reality dashboard for 2 owned books.

No wallet addresses, private paths, user PII, checkout switches or side effects.
Unknown providers/delivery are UNKNOWN rather than green/success.
"""
import json
import os
import pathlib
import stat
import time
from datetime import datetime, timezone

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



def _worker_health():
    """Read only a bounded worker heartbeat; never load payments or customer data."""
    status = {
        "present": False, "healthy": False, "state": "unknown",
        "last_utc": "—", "age_seconds": None,
        "pending": 0, "matched": 0, "paid": 0, "rejected": 0,
        "error_type": "",
    }
    name = pathlib.Path("/home/zomorod2/.mpw-commerce-two-books/worker-heartbeat.json")
    try:
        fd = os.open(str(name), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_size < 10 or meta.st_size > 4096:
                return status
            with os.fdopen(fd, "r", encoding="utf8") as handle:
                fd = -1
                record = json.load(handle)
        finally:
            if fd >= 0:
                os.close(fd)
        if type(record) is not dict or record.get("schema") != 1:
            return status
        timestamp = record.get("utc_epoch")
        if type(timestamp) is not int:
            return status
        age = int(time.time()) - timestamp
        if age < -30 or age > 86400:
            return status
        state = str(record.get("state", "unknown"))[:32]
        fresh = age <= 180 and age >= -30
        status.update({
            "present": True,
            "healthy": fresh and record.get("healthy") is True and state in ("idle", "scanned", "disabled"),
            "state": state,
            "last_utc": datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "age_seconds": max(0, age),
            "pending": int(record.get("pending", 0)),
            "matched": int(record.get("matched", 0)),
            "paid": int(record.get("paid", 0)),
            "rejected": int(record.get("rejected", 0)),
            "error_type": str(record.get("error_type", ""))[:60],
        })
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        pass
    return status


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
    # A successful order status is not independent proof of a chain payment.
    commerce_count = None
    commerce_by_status = {}
    verified_receipts_count = None
    confirmed_revenue_usd = None
    fulfillment_count = None
    fulfillments_by_status = {}
    try:
        from decimal import Decimal
        from django.db.models import Sum
        invoice_model = apps.get_model("mpw_commerce", "CommerceInvoice")
        receipt_model = apps.get_model("mpw_commerce", "CommerceReceipt")
        fulfillment_model = apps.get_model("mpw_commerce", "CommerceFulfillment")
        invoices = invoice_model.objects.filter(order_id__in=order_ids)
        commerce_count = invoices.count()
        for value in invoices.values_list("status", flat=True):
            commerce_by_status[value] = commerce_by_status.get(value, 0) + 1
        verified = receipt_model.objects.filter(
            invoice_id__in=invoices.values_list("id", flat=True),
            finalized_at__isnull=False,
        ).exclude(evidence_digest="")
        verified_receipts_count = verified.count()
        confirmed = invoices.filter(
            id__in=verified.values_list("invoice_id", flat=True),
            status=invoice_model.Status.PAID,
        )
        confirmed_revenue_usd = str(
            confirmed.aggregate(amount=Sum("total_usd"))["amount"] or Decimal("0.00")
        )
        fulfilled = fulfillment_model.objects.filter(
            item__order_id__in=order_ids,
            item__product_id__in=BOOK_IDS,
        )
        fulfillment_count = fulfilled.count()
        for value in fulfilled.values_list("status", flat=True):
            fulfillments_by_status[value] = fulfillments_by_status.get(value, 0) + 1
    except LookupError:
        # Preserve honest unknown status when commerce V2 is not installed.
        pass
    return {
        "books": books,
        "worker": _worker_health(),
        "flags": active_flags,
        "all_gateway_flags_enabled": all(active_flags.values()),
        "orders_total": orders.count(),
        "orders_by_status": by_status,
        "intents_total": intents.count(),
        "intents_by_status": intent_status,
        "native_invoices_count": native_invoices,
        "commerce_invoices_count": commerce_count,
        "commerce_invoices_by_status": commerce_by_status,
        "verified_receipts_count": verified_receipts_count,
        "confirmed_revenue_usd": confirmed_revenue_usd,
        "commerce_fulfillment_count": fulfillment_count,
        "commerce_fulfillments_by_status": fulfillments_by_status,
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
