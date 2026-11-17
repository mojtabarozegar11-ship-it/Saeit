"""21-language, nonpayable MojProp CRM interest form.

This GET-only page POSTs to the existing, independently tested main Django
mojprop_intake endpoint, with the very same CSRF and idempotency contract.
It creates no direct database writes, invoices, funded accounts or trades.
"""
from uuid import uuid4

from django.http import Http404, HttpResponseNotAllowed
from django.middleware.csrf import get_token
from django.shortcuts import render

from .world20_views import _HOSTS, world_catalog


def localized_prop_interest(request, lang):
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Invalid MojPlayWin host") from exc
    if host not in _HOSTS or not request.is_secure():
        raise Http404("MojPlayWin HTTPS required")
    if request.META.get("QUERY_STRING", ""):
        raise Http404("No personal data or campaign queries allowed")
    data = world_catalog()["locales"]
    if lang not in data:
        raise Http404("Unsupported language")
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    copy = data[lang]
    response = render(
        request, "mojplaywin/world20_prop_interest.html",
        {
            "locale": lang, "copy": copy, "csrf_value": get_token(request),
            "nonce": str(uuid4()),
            "notes": (
                "Prelaunch interest only: MOJ-PROP-01 (proposed real "
                "proprietary trading CHALLENGE). No 30 TRX payment, no "
                "funded account, no contract accepted. Please send legal "
                "eligibility, country, KYC, risk and refund information. "
                "Preferred language: " + lang + ". " + copy["prop_body"]
            ),
        },
        content_type="text/html; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Frame-Options"] = "DENY"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'; "
        "object-src 'none'; connect-src 'none'"
    )
    if request.method == "HEAD":
        response.content = b""
    return response
