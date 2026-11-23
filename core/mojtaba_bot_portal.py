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

from core.customer_sales_faq import local_sales_answer

# Public visitors may select ONLY predefined informational topics, never
# arbitrary chat text, privileged commands, customer data or a paid API.
_PUBLIC_HELP_PROMPTS = {
    "prop": "MOJ PROP Starter30",
    "signals": "trading signals",
    "store": "digital store",
}


@never_cache
@xframe_options_deny
@require_GET
def mojtaba_bot_portal(request):
    """Render a fail-closed portal; never start a worker or task on GET."""
    signed_in = bool(
        request.user.is_authenticated and request.user.is_active
    )
    # The legacy paid release flag is insufficient to attest final rules,
    # exclusive invoice recipient, reserved payouts or verified buyer email.
    # Do not re-expose that unsafe route through the central assistant portal.
    # Unpaid CRM requests remain available without a DB or provider preflight.

    selected_topic = request.GET.get("topic", "")
    prompt = _PUBLIC_HELP_PROMPTS.get(selected_topic)
    public_answer = local_sales_answer(prompt) if prompt else None
    nonce = token_urlsafe(24)
    context = {
        "public_help_topic": selected_topic if prompt else "",
        "public_help_answer": public_answer or "",
        "signed_in": signed_in,
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
