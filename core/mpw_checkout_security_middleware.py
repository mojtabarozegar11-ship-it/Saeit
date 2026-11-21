"""Django-side security headers for MojPlayWin's EXACT guest checkout GETs.

This is defense in depth, not a replacement for the buyer-email, CSRF,
immutable order ownership, independent finality or paid entitlement guards.
When the page is served by Apache static fallback or a separate Passenger
app this middleware does not run; never mistake source CI for a live fix.
"""
from __future__ import annotations

import re

HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
CHECKOUT_ROUTE = re.compile(
    r"\A(?:/store/product/|/commerce/book/)[1-9][0-9]{0,8}/"
    r"(?:checkout/)?\Z"
)
STRICT_CSP = (
    "default-src 'self'; script-src 'none'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
    "img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; connect-src 'self'"
)
NO_STORE = "private, no-store, max-age=0"


def _exact_route(path):
    """Accept only real checkout shapes, not a product detail or prefix."""
    if type(path) is not str or not path.isascii() or len(path) > 90:
        return False
    if path.startswith("/store/product/"):
        return bool(re.fullmatch(r"/store/product/[1-9][0-9]{0,8}/checkout/", path))
    return bool(re.fullmatch(r"/commerce/book/[1-9][0-9]{0,8}/", path))


def _owned_html_checkout(request, response):
    try:
        host = request.get_host()
    except (ValueError, AttributeError):
        return False
    if type(host) is not str or host.lower().split(":", 1)[0] not in HOSTS:
        return False
    if getattr(request, "method", None) not in ("GET", "HEAD"):
        return False
    if not _exact_route(getattr(request, "path", None)):
        return False
    if getattr(response, "status_code", None) != 200:
        return False
    try:
        content_type = response.get("Content-Type", "")
    except (ValueError, TypeError, AttributeError):
        return False
    return isinstance(content_type, str) and (
        content_type.lower().split(";", 1)[0].strip() == "text/html"
    )


class MojPlayWinCheckoutSecurityMiddleware:
    """Tighten only 200 HTML GET/HEAD checkout responses for the two MPW hosts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not _owned_html_checkout(request, response):
            return response

        # One fixed policy, never merge untrusted/duplicated script directives.
        # Inline JS is intentionally disabled for the owner-required email form.
        response["Content-Security-Policy"] = STRICT_CSP
        response["Cache-Control"] = NO_STORE
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "no-referrer"

        # Keep prior Vary dimensions. Add Host to prevent host-specific CSP
        # from being cached and replayed on the company-domain response.
        existing_vary = response.get("Vary", "") or ""
        parts = [token.strip() for token in existing_vary.split(",") if token.strip()]
        if "*" not in parts and not any(token.casefold() == "host" for token in parts):
            parts.append("Host")
        if parts:
            response["Vary"] = ", ".join(parts)
        return response
