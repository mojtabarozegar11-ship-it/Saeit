"""Protected TRX invoice/status/reconciliation/paid-download URL bridge.

All financial decisions and guest ownership remain with the owner-reviewed
private cPanel commercial handlers. No mocked receipts or payment confirmations.
"""
from __future__ import annotations

from importlib import import_module

from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST


REVIEWED_ROUTES = {
    "show_invoice": "/commerce/trx-easy/invoice/<str:invoice_id>/",
    "invoice_status": "/commerce/trx-easy/invoice/<str:invoice_id>/status/",
    "reconcile_invoice": "/commerce/trx-easy/invoice/<str:invoice_id>/reconcile/",
    "download_paid": "/commerce/trx-easy/download/<str:receipt_id>/",
}


def _reviewed_handler(name):
    if name not in REVIEWED_ROUTES:
        return None
    try:
        commercial = import_module("services.mpw_trx_commercial_web")
    except Exception:
        return None
    if getattr(commercial, "_mpw_guest_checkout_installed", False) is not True:
        return None
    patterns = getattr(commercial, "COMMERCIAL_URLPATTERNS", None)
    if type(patterns) is not tuple:
        return None
    target = REVIEWED_ROUTES[name]
    views = [
        entry[1] for entry in patterns
        if type(entry) is tuple and len(entry) == 2
        and entry[0] == target and callable(entry[1])
    ]
    if len(views) != 1:
        return None
    view = views[0]
    if (getattr(view, "__name__", None) != name
            or getattr(view, "__module__", None)
            != "services.mpw_trx_guest_commerce"
            or getattr(view, "csrf_exempt", False)):
        return None
    return view


def _unavailable():
    response = HttpResponse(
        "The secure invoice service is temporarily unavailable. "
        "If you have already paid, do not send funds again.",
        status=503, content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "same-origin"
    return response


def _delegate(request, route, **kwargs):
    if (not request.is_secure()
            or request.get_host().split(":", 1)[0].lower()
            not in ("mojplaywin.com", "www.mojplaywin.com")
            or len(kwargs) != 1
            or any(type(value) is not str or not value or len(value) > 256
                   or not value.isprintable() for value in kwargs.values())):
        raise Http404
    handler = _reviewed_handler(route)
    if handler is None:
        return _unavailable()
    # Signed-session ownership, chain reconciliation, idempotency and
    # download entitlement must be enforced by the original guest handler.
    return handler(request, **kwargs)


@never_cache
@require_GET
def show_invoice(request, invoice_id):
    return _delegate(request, "show_invoice", invoice_id=invoice_id)


@never_cache
@require_GET
def invoice_status(request, invoice_id):
    return _delegate(request, "invoice_status", invoice_id=invoice_id)


@never_cache
@csrf_protect
@require_POST
def reconcile_invoice(request, invoice_id):
    return _delegate(request, "reconcile_invoice", invoice_id=invoice_id)


@never_cache
@require_GET
def download_paid(request, receipt_id):
    return _delegate(request, "download_paid", receipt_id=receipt_id)
