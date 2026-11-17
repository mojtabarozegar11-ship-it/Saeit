"""Exact host- and HTTPS-scoped, GET-only v1.4.1 prelaunch information.

This module is not a checkout, application or marketing consent endpoint.
All old /moj-prop/ and /moj-prop-interest/ routes stay unchanged; this new
independent root route MUST NOT be confused with the v1.2 form or paid sales.
Owner-controlled production deployment is expressly outside this module.
"""
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import render
from django.views.decorators.cache import never_cache

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
    # A template-only page: no user input is parsed, recorded or echoed.
    if request.META.get("QUERY_STRING", ""):
        raise Http404("Unexpected query data")
    response = render(
        request, "moj-prop-plan1-v141-prelaunch/index.html",
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
    return response
