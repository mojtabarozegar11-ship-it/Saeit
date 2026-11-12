"""Fail-closed invoice creation route for the independently installed TRX backend.

This module intentionally does not create invoices, accept transaction hashes,
set receiver addresses, or release a paid file. It can only delegate a request
to the exact CSRF-protected guest handler in the owner-reviewed cPanel module.
"""
from __future__ import annotations

from importlib import import_module

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

START_ROUTE = "/commerce/trx-easy/start/<int:product_id>/"


def _reviewed_invoice_start():
    """Resolve the already-patched commercial POST route, not a raw _start_order."""
    try:
        commercial = import_module("services.mpw_trx_commercial_web")
    except Exception:
        return None
    if getattr(commercial, "_mpw_guest_checkout_installed", False) is not True:
        return None
    patterns = getattr(commercial, "COMMERCIAL_URLPATTERNS", None)
    if type(patterns) is not tuple:
        return None
    matches = [entry[1] for entry in patterns if (
        type(entry) is tuple and len(entry) == 2
        and entry[0] == START_ROUTE and callable(entry[1])
    )]
    if len(matches) != 1:
        return None
    handler = matches[0]
    if (getattr(handler, "__name__", None) != "start_order"
            or getattr(handler, "__module__", None)
            != "services.mpw_trx_guest_commerce"
            or getattr(handler, "csrf_exempt", False)):
        return None
    return handler


def invoice_start_ready():
    """Route/handler installation is proved; receiver and funds are NOT proved."""
    return _reviewed_invoice_start() is not None


def _unavailable():
    response = HttpResponse(
        "TRX invoice creation is temporarily unavailable. "
        "No invoice was created. Do not send funds.",
        status=503, content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@never_cache
@csrf_protect
@require_POST
def start_order(request, product_id):
    if (not request.is_secure()
            or request.get_host().split(":", 1)[0].lower()
            not in ("mojplaywin.com", "www.mojplaywin.com")
            or type(product_id) is not int or product_id <= 0):
        raise Http404
    ids = getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ())
    if (getattr(settings, "MPW_WALLETLESS_TRX_PUBLIC_ENABLED", False) is not True
            or type(ids) not in (list, tuple, set, frozenset)
            or product_id not in ids):
        return _unavailable()
    handler = _reviewed_invoice_start()
    if handler is None:
        return _unavailable()
    # The original guest handler owns order identity, rights checks, atomic
    # invoice recording, receiver validation and paid-file entitlement.
    return handler(request, product_id=product_id)
