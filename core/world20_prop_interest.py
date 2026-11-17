"""21-language nonpayable MOJ-PROP-01 intake and private receipt.

The canonical, CSRF-protected MojProp CRM endpoint remains authoritative.
A localized HTML POST delegates to it; no second write path, payment
authorization, account creation or email delivery exists in this module.
"""
import json
from uuid import uuid4

from django.http import Http404, HttpResponseNotAllowed
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect

from .world20_views import _HOSTS, world_catalog


def _secure(response, language, *, private_receipt=False):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Content-Language"] = language
    response["Referrer-Policy"] = ("no-referrer" if private_receipt else "same-origin")
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Frame-Options"] = "DENY"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'; "
        "object-src 'none'; connect-src 'none'"
    )
    return response


def _form_response(request, lang, copy, *, failed=False, status=200):
    context = {
        "locale": lang, "copy": copy, "failed": failed,
        "csrf_value": get_token(request), "nonce": str(uuid4()),
        "notes": (
            "Prelaunch interest only: MOJ-PROP-01 (proposed real "
            "proprietary trading CHALLENGE). No 30 TRX payment, no "
            "funded account, no contract accepted. Please send legal "
            "eligibility, country, KYC, risk and refund information. "
            "Preferred language: " + lang + ". " + copy["prop_body"]
        ),
    }
    return _secure(render(
        request, "mojplaywin/world20_prop_interest.html", context,
        status=status, content_type="text/html; charset=utf-8",
    ), lang)


@csrf_protect
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
    if request.method not in ("GET", "HEAD", "POST"):
        return _secure(HttpResponseNotAllowed(["GET", "HEAD", "POST"]), lang)
    copy = data[lang]
    if request.method in ("GET", "HEAD"):
        response = _form_response(request, lang, copy)
        if request.method == "HEAD":
            response.content = b""
        return response

    # Existing endpoint is the sole CRM writer and validates the bounded
    # form, idempotency UUIDv4, consent, email, honeypot and throttling.
    # Its Django CSRF decorator also runs. No duplicate application table.
    from .mojprop_views import mojprop_intake
    from .mojprop_receipts import verify_receipt_token

    api_response = mojprop_intake(request)
    try:
        data = json.loads(api_response.content.decode("utf-8"))
    except (UnicodeError, ValueError, AttributeError, TypeError):
        data = {}
    success = (type(data) is dict and data.get("ok") is True
               and api_response.status_code in (200, 201)
               and type(data.get("request_id")) is str
               and type(data.get("receipt_token")) is str
               and verify_receipt_token(data["receipt_token"])
                   == data["request_id"])
    if success:
        response = render(request, "mojplaywin/world20_prop_receipt.html", {
            "locale": lang, "copy": copy,
            "reused": data.get("reused") is True,
            "reference": data["request_id"],
            "private_receipt": data["receipt_token"],
        }, status=api_response.status_code, content_type="text/html; charset=utf-8")
        return _secure(response, lang, private_receipt=True)

    status = api_response.status_code
    # Fail closed on malformed or unexpected downstream success responses.
    if status < 400:
        status = 503
    response = _form_response(request, lang, copy, failed=True, status=status)
    if api_response.has_header("Retry-After"):
        response["Retry-After"] = api_response["Retry-After"]
    return response
