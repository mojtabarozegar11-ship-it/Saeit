"""Same-origin entry point for the existing authenticated master-chat API.

This view grants no new backend capability or owner permissions. A public visitor
gets only sign-in and existing inquiry links; authenticated users may access
the already-protected /api/master-chat/ endpoint through their Django session.
"""
from secrets import token_urlsafe

from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.http import require_GET


@never_cache
@xframe_options_deny
@require_GET
def mojtaba_bot_portal(request):
    """Render a fail-closed portal; never start a worker or task on GET."""
    signed_in = bool(
        request.user.is_authenticated and request.user.is_active
    )
    # Advertising an invoice route is allowed only when its real existing
    # server release gates and local provider configuration are available.
    # This preflight performs no on-chain RPC, charge or database write.
    starter30_checkout_available = False
    try:
        from prop_firm.starter30_live import (
            release_is_open, verify_pre_invoice_configuration,
        )
        if release_is_open():
            verify_pre_invoice_configuration()
            starter30_checkout_available = True
    except Exception:
        # Payment is fail-closed. The unpaid request remains available.
        starter30_checkout_available = False

    nonce = token_urlsafe(24)
    context = {
        "signed_in": signed_in,
        "starter30_checkout_available": starter30_checkout_available,
        "nonce": nonce,
        "csrf_for_chat": get_token(request) if signed_in else "",
    }
    response = render(request, "core/mojtaba_bot_portal.html", context)
    response["Content-Security-Policy"] = (
        "default-src 'none'; "
        "base-uri 'none'; object-src 'none'; "
        "frame-ancestors 'none'; form-action 'self'; "
        "connect-src 'self'; img-src 'self'; "
        "style-src 'nonce-" + nonce + "'; "
        "script-src 'nonce-" + nonce + "'"
    )
    response["Referrer-Policy"] = "same-origin"
    response["X-Content-Type-Options"] = "nosniff"
    if signed_in:
        # The private operator-only chat must never inherit public SEO headers.
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
