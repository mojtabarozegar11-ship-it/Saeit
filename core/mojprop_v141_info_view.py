"""Exact host- and HTTPS-scoped, GET-only v1.4.1 prelaunch information.

This module is not a checkout, application or marketing consent endpoint.
All old /moj-prop/ and /moj-prop-interest/ routes stay unchanged; this new
independent root route MUST NOT be confused with the v1.2 form or paid sales.
Owner-controlled production deployment is expressly outside this module.
"""
from django.conf import settings
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from prop_firm.mojprop_v141_info_i18n import info_context
from prop_firm.moj_prop_page import SUPPORTED_CODES

_ALLOWED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


@never_cache
def moj_prop_v141_public_info(request):
    """Show fixed draft terms in EN/FA without changing customer state."""
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Unavailable host") from exc
    if host not in _ALLOWED_HOSTS or request.is_secure() is not True:
        raise Http404("Only MojPlayWin HTTPS is permitted")
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    # Only a single recognized language selection is allowed, with no PII.
    if request.META.get("QUERY_STRING", ""):
        if set(request.GET) != {"lang"} or len(request.GET.getlist("lang")) != 1:
            raise Http404("Unexpected query data")
        lang = request.GET["lang"]
        if lang not in SUPPORTED_CODES:
            raise Http404("Unsupported language")
        response = render(
            request, "moj-prop-plan1-v141-prelaunch/info_20.html",
            {**info_context(lang), "interest_enabled": getattr(
                settings, "MOJ_PROP_V141_INTEREST_ENABLED", False) is True},
            content_type="text/html; charset=utf-8",
        )
    else:
        response = render(
            request, "moj-prop-plan1-v141-prelaunch/index.html",
            {"interest_enabled": getattr(settings, "MOJ_PROP_V141_INTEREST_ENABLED", False) is True},
            content_type="text/html; charset=utf-8",
        )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Frame-Options"] = "DENY"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; object-src 'none'; "
        "frame-ancestors 'none'; connect-src 'none'"
    )
    if request.method == "HEAD":
        response.content = b""
    return response
