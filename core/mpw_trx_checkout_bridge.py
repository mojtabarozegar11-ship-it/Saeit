"""No-email MojPlayWin checkout routing bridge to the reviewed cPanel handler.

Never implements or duplicates TRX invoicing, settlement or fulfillment.
Only an already-installed guest adapter may serve the public checkout page.
"""
from __future__ import annotations

from importlib import import_module

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .mpw_trx_invoice_bridge import invoice_start_ready


def _reviewed_checkout():
    try:
        module = import_module("services.mpw_trx_public_pages")
    except Exception:
        # An unavailable or broken optional commerce source must not turn
        # the public product page into a 500 or expose import details.
        # This is a fail-closed availability result, not authorization.
        return None
    handler = getattr(module, "product_checkout", None)
    if (not callable(handler)
            or getattr(handler, "__name__", None) != "product_checkout"
            or getattr(handler, "__module__", None) != "services.mpw_trx_guest_commerce"):
        return None
    return handler


def backend_ready():
    """Flag and reviewed adapter availability; never proof of invoice settlement."""
    if getattr(settings, "MPW_WALLETLESS_TRX_PUBLIC_ENABLED", False) is not True:
        return False
    # A product form without its protected invoice POST endpoint is a dead
    # end, not a commercially usable checkout. Require both reviewed handlers.
    return _reviewed_checkout() is not None and invoice_start_ready()


def _unavailable():
    response = HttpResponse(
        "Secure TRX checkout is temporarily unavailable. "
        "No invoice was created. Please do not send funds.",
        status=503, content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "same-origin"
    return response


@never_cache
@require_GET
def product_checkout(request, product_id):
    if (not request.is_secure()
            or request.get_host().split(":")[0].lower()
            not in ("mojplaywin.com", "www.mojplaywin.com")
            or type(product_id) is not int or product_id <= 0):
        raise Http404
    ids = getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ())
    if not isinstance(ids, (list, tuple, set, frozenset)) or product_id not in ids:
        raise Http404
    # A configured product ID is not a mandate to accept payment. An explicit
    # public switch is required in addition to backend and owner-rights checks.
    if getattr(settings, "MPW_WALLETLESS_TRX_PUBLIC_ENABLED", False) is not True:
        return _unavailable()
    handler = _reviewed_checkout()
    if handler is None or not invoice_start_ready():
        return _unavailable()
    # Authorization, CSRF, receiver readiness and rights checks remain owned
    # by the reviewed guest adapter and existing commercial backend.
    return handler(request, product_id)
