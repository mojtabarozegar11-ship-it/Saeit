"""Buyer-only recovery of previously purchased digital downloads.

This endpoint never settles a payment or grants new rights. Entitlements
are established by the independently verified chain receipt, ledger and
fulfillment record, and the underlying private-file endpoint checks them
again for every download.
"""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.models import OrderItem
from .entitlements import can_access_purchased_digital_item

ALLOWED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


@login_required
@never_cache
@require_GET
def purchased_downloads(request):
    if (
        getattr(settings, "MPW_COMMERCE_DOWNLOADS_ENABLED", False) is not True
        or not request.is_secure()
        or request.get_host().split(":")[0].lower() not in ALLOWED_HOSTS
        or not request.user.is_active
    ):
        raise Http404("Purchased downloads unavailable")

    candidates = (
        OrderItem.objects.select_related("product")
        .filter(
            order__customer_id=request.user.pk,
            order__status="paid",
            product__product_type__in=("digital", "digital_book"),
        )
        .order_by("-id")[:200]
    )
    approved = []
    for item in candidates:
        # No account may enumerate or retrieve other customers' orders;
        # paid status alone is not enough for a download link.
        if can_access_purchased_digital_item(item.pk, request.user.pk):
            approved.append({
                "title": item.product.title,
                "url": reverse("mpw_commerce:download", kwargs={"item_id": item.pk}),
            })
    response = render(
        request, "mpw_commerce/purchased_downloads.html", {"purchases": approved}
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
