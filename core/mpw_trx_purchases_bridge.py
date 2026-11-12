"""Buyer invoice/recovery GET route delegated to the installed guest adapter.

New-sale feature flags must not disable access to legitimately paid orders.
No public invoice lookup, transaction submission or private file access here.
"""
from __future__ import annotations

from importlib import import_module

from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def _reviewed_purchases():
    try:
        module = import_module("services.mpw_trx_public_pages")
    except Exception:
        return None
    handler = getattr(module, "purchases", None)
    if (not callable(handler)
            or getattr(handler, "__name__", None) != "purchases"
            or getattr(handler, "__module__", None)
            != "services.mpw_trx_guest_commerce"
            or getattr(handler, "csrf_exempt", False)):
        return None
    return handler


@never_cache
@require_GET
def purchases(request):
    if (not request.is_secure()
            or request.get_host().split(":", 1)[0].lower()
            not in ("mojplaywin.com", "www.mojplaywin.com")):
        raise Http404
    view = _reviewed_purchases()
    if view is None:
        response = HttpResponse(
            "Purchase recovery is temporarily unavailable. "
            "If you already paid, do not pay again. "
            "Keep your invoice reference and transaction hash private.",
            status=503, content_type="text/plain; charset=utf-8",
        )
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["X-Robots-Tag"] = "noindex, nofollow"
        response["Referrer-Policy"] = "same-origin"
        return response
    # The original handler checks the signed guest session, invoice ownership
    # and purchased-file entitlements. The route never lists arbitrary orders.
    return view(request)
