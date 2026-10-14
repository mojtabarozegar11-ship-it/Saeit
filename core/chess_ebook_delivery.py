"""Fail-closed MojPlayWin paid-download endpoint.

Staged module: do not add to production URLconf until payment/fulfilment tests pass.
Never place the book under public_html or a publicly served media directory.
"""
import hashlib
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product

BOOK_PRODUCT_ID = "mojplaywin-chess-improvement-2026"
PDF_PATH = Path("/home/zomorod2/MojPlayWin_Private_Assets/chess-improvement-2026/MojPlayWin_Science_and_Practice_of_Chess_Improvement.pdf")
EXPECTED_SHA256 = "d284d559bfac931cffe11e97561ac442d63dae5d8eda4bc04e84dd2c26022a1b"
EXPECTED_BYTES = 432386
EXPECTED_PRICE = "7.50"
DOWNLOAD_NAME = "The_Science_and_Practice_of_Chess_Improvement.pdf"


def has_verified_purchase(user, order_id):
    """Only a settled, provider-authenticated order may receive the private PDF.

    Intent status alone is insufficient: require a verified successful webhook
    and corresponding ledger entry bound to the same order and amount.
    """
    if not user or not user.is_authenticated:
        return False
    try:
        product = Product.objects.get(pk=72)
        if not product.active:
            return False
        metadata = product.metadata if isinstance(product.metadata, dict) else {}
        if metadata.get("product_id") != BOOK_PRODUCT_ID:
            return False
        if metadata.get("asset_verified") is not True or metadata.get("payment_live") is not True:
            return False
        if product.currency != "USD" or str(product.price) != EXPECTED_PRICE:
            return False

        order = Order.objects.filter(pk=order_id, customer_id=user.pk, status="paid").first()
        if order is None or order.currency != "USD" or str(order.total) != EXPECTED_PRICE:
            return False

        if not OrderItem.objects.filter(
            order=order, product=product, quantity=1, currency="USD",
            unit_price=product.price,
        ).exists():
            return False
        if OrderItem.objects.filter(order=order).exclude(product=product).exists():
            return False

        intent = PaymentIntent.objects.filter(
            order=order, status="succeeded", amount=order.total, currency=order.currency
        ).first()
        if intent is None or intent.provider in ("", "not_configured", None) or not intent.provider_reference:
            return False
        if not PaymentWebhookEvent.objects.filter(
            payment_intent=intent,
            provider=intent.provider,
            event_type="payment.succeeded",
            status="processed",
        ).exists():
            return False
        if not LedgerEntry.objects.filter(
            order=order,
            payment_intent=intent,
            entry_type="payment",
            amount=order.total,
            currency=order.currency,
        ).exists():
            return False
        return True
    except (Product.DoesNotExist, ValueError, TypeError):
        return False


@never_cache
@require_GET
@login_required
def chess_ebook_download(request, order_id):
    if not has_verified_purchase(request.user, order_id):
        raise Http404("Download not available")
    if not PDF_PATH.is_file() or PDF_PATH.is_symlink():
        raise Http404("Verified PDF missing")
    if PDF_PATH.stat().st_size != EXPECTED_BYTES:
        raise Http404("Verified PDF size mismatch")
    with PDF_PATH.open("rb") as check:
        if hashlib.sha256(check.read()).hexdigest() != EXPECTED_SHA256:
            raise Http404("Verified PDF digest mismatch")

    response = FileResponse(PDF_PATH.open("rb"), as_attachment=True, filename=DOWNLOAD_NAME,
                            content_type="application/pdf")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response
