"""Buyer-authenticated exact MOJ-PROP-01 native TRX invoice and receipt.

Private, no advertisements, no public checkout, no wallet signatures required.
No user-initiated payment writes, transfers, or order issuance. An invoice can
only originate through the independently vetted private merchant service.
"""
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from prop_firm.plan1_v141_native_checkout import (
    CheckoutRejected, _check_signed_order, _release_enabled,
)
from prop_firm.plan1_v141_native_payment_models import PropV141NativeOrder


_REF = re.compile(r"MOJPROP01-[0-9A-F]{32}\Z")
_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


@login_required
@never_cache
def moj_prop_v141_native_invoice(request, reference):
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Invalid merchant host") from exc
    if (request.is_secure() is not True or host not in _HOSTS
            or _REF.fullmatch(reference) is None
            or getattr(request.user, "is_active", False) is not True
            or request.META.get("QUERY_STRING")):
        raise Http404("No available private invoice")
    order = (PropV141NativeOrder.objects
             .select_related("native_receipt", "native_receipt__book")
             .filter(buyer_id=request.user.pk, reference=reference)
             .first())
    if order is None:
        raise Http404("No matching buyer order")
    try:
        _check_signed_order(order)
    except CheckoutRejected as exc:
        raise Http404("Invalid merchant invoice signature") from exc
    ready_to_pay = (
        order.status == "issued"
        and order.expires_at > timezone.now()
        and _release_enabled()
    )
    paid_receipt = (
        order.native_receipt if order.status == "settled" else None
    )
    # Never expose wallet if payment is closed. Read-only receipts remain
    # accessible to rightful purchasers even after new billing is paused.
    response = render(request, "mojprop/v141-native-trx-invoice.html", {
        "order": order,
        "ready_to_pay": ready_to_pay,
        "receiver": order.recipient if ready_to_pay else "",
        "amount_trx": "30.000000" if ready_to_pay else "",
        "receipt": paid_receipt,
        "challenge_statement_enabled": (
            paid_receipt is not None and
            getattr(settings, "MOJ_PROP_V141_PORTFOLIO_ENABLED", False) is True
        ),
    })
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'; connect-src 'none'"
    )
    if request.method == "HEAD":
        response.content = b""
    return response
