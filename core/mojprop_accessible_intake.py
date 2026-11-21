"""Accessible, JavaScript-free Moj Prop public request and non-payment receipt.

The same existing Django intake endpoint creates the CRM request; this module
only renders secure HTML. No SMTP, invoices, wallet address, downloads, trade,
paid checkout, external scripts, third-party CSS, or release side effects.
"""
from html import escape
from uuid import uuid4

from django.http import HttpResponse
from django.middleware.csrf import get_token

from .models import MojPropRequest

ACTION = "/moj-prop-intake/?format=html"


def _private_html(title, body, *, status=200):
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>' + escape(title) + ' | Moj Prop</title>'
        '</head><body><main><h1>' + escape(title) + '</h1>'
        + body + '</main></body></html>'
    )
    response = HttpResponse(document, status=status,
                            content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Content-Security-Policy"] = (
        "default-src 'none'; form-action 'self'; base-uri 'none'; "
        "frame-ancestors 'none'"
    )
    return response


def _safe_service_prefill(request, *, allow_starter30_post_retry=False):
    """Accept bounded, untrusted Plan 1 prelaunch navigation without a checkout.

    Query strings are untrusted navigation hints, never prices, accepted
    contract terms, a customer identity, payment proof or persisted records.
    """
    # Preserve the original GET-only contract for normal callers. The form
    # renderer may explicitly recover *only* the fixed Starter30 navigation
    # hint after a failed POST; it never feeds these hints to the CRM writer.
    if request.method != "GET":
        if not (
            allow_starter30_post_retry
            and request.method == "POST"
            and request.GET.getlist("package") == ["starter-30-trx"]
        ):
            return None, ""
    services = request.GET.getlist("service")
    packages = request.GET.getlist("package")
    if len(services) > 1 or len(packages) > 1:
        return None, ""
    service = services[0] if services else None
    routes = {code for code, _ in MojPropRequest.ROUTE_CHOICES if code != "digital"}
    if service not in routes:
        return None, ""
    if packages:
        if service != "blueprint":
            return None, ""
        if packages == ["moj-prop-01"]:
            # Navigation hint ONLY: buyer edits notes; the CRM receipt is
            # not a SKU-authenticated paid order or funded enrollment.
            return service, (
                "Prelaunch interest only: MOJ-PROP-01 (two-stage proprietary "
                "funded-trading CHALLENGE; proposed 30 native TRX fee is "
                "NOT payable at this time).\n"
                "Please send legal eligibility, country availability, "
                "risk rules, KYC and refund terms for MOJ-PROP-01. "
                "I understand the evaluation is simulated and an actual "
                "company-funded initial USD 100 account after passing "
                "requires independent capital, broker agreement and "
                "legal approval; no payment, account or return is promised."
            )
        if packages != ["starter-30-trx"]:
            return None, ""
        # This is still a buyer-editable, unverified request. The existing
        # offer-draft classifier recognises the exact leading product line;
        # it never authorises an invoice or a paid entitlement.
        return service, (
            "Requested canonical product: MOJPROP-STARTER30 "
            "(one-time indicative 30 native TRX; written terms and verified "
            "lawful invoice required; NOT paid)\n"
            "Please send written terms for the 60-day simulated challenge "
            "journal and individual educational feedback. The approved profile "
            "uses a virtual $1,000 reference balance, not a funded account, "
            "live trade, payment or profit guarantee."
        )
    return service, ""


def _attribution_hidden_fields(request):
    """Carry bounded campaign attribution through the HTML POST without PII."""
    fields = []
    for name in ("utm_source", "utm_medium", "utm_campaign", "utm_content"):
        value = request.GET.get(name, "") or request.POST.get(name, "")
        fields.append(
            '<input type="hidden" name="' + escape(name, quote=True) +
            '" value="' + escape(str(value).strip()[:80], quote=True) + '">'
        )
    return "".join(fields)


def _options(choices, *, selected=None):
    return "".join(
        '<option value="' + escape(value, quote=True) + '"' +
        (' selected' if value == selected else '') + '>' +
        escape(title) + '</option>'
        for value, title in choices if value != 'digital'
    )


def _verified_public_campaign_suffix(request):
    """Preserve one known public organic campaign in the POST URL only.

    These are marketing labels, NOT identity evidence, payment authority or
    conversion proof. Reject duplicates and all arbitrary campaign parameters.
    Never echo user-supplied values, emails, token, referrer or customer PII.
    """
    fixed = (
        ("utm_source", "facebook"),
        ("utm_medium", "organic_social"),
        ("utm_campaign", "starter30_qualified_enquiry_20261121"),
    )
    if any(request.GET.getlist(key) != [expected] for key, expected in fixed):
        return ""
    if any(key.startswith("utm_") and key not in dict(fixed) for key in request.GET):
        return ""
    return "".join("&amp;" + key + "=" + expected for key, expected in fixed)


def request_form(request, *, error=None, status=200):
    """Always provide a fresh CSRF-protected form; never echo PII on errors."""
    csrf = escape(get_token(request), quote=True)
    selected, prefill_notes = _safe_service_prefill(
        request,
        allow_starter30_post_retry=(request.method == "POST" and error is not None),
    )
    message = ('<p role="alert">' + escape(error) + '</p>') if error else ''
    # Retain the fixed product hint on the form POST, including validation
    # failures, without reflecting untrusted campaign data or buyer PII.
    is_starter30 = prefill_notes.startswith("Requested canonical product: MOJPROP-STARTER30 ")
    action = (ACTION + "&amp;service=blueprint&amp;package=starter-30-trx"
              + _verified_public_campaign_suffix(request)
              if is_starter30 else ACTION)
    if prefill_notes.startswith("Prelaunch interest only: MOJ-PROP-01"):
        message += (
            '<p><strong>MOJ-PROP-01 funded-trading challenge — PRELAUNCH.</strong> '
            '30 TRX is a proposed future challenge fee, not a purchase today. '
            'The two evaluation stages are simulated. A real funded account '
            'is conditional on a verified broker, company capital, legal '
            'eligibility and written customer terms. This form takes no '
            'payment and creates no challenge registration.</p>'
        )
    elif is_starter30:
        message += ('<p>Starter30 is a <strong>free request for written terms only</strong>; '
                    'this form does not issue an invoice, collect a fee, enroll a '
                    'challenge or activate a trading account.</p>')
    form = (
        '<p>Request a written, manually reviewed service proposal. '
        'No payment, live account or return is promised.</p>'
        + message +
        '<form method="post" action="' + action + '" '
        'enctype="application/x-www-form-urlencoded">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrf + '">'
        + _attribution_hidden_fields(request) +
        '<p><label>Your name <input name="name" autocomplete="name" '
        'required minlength="2" maxlength="200"></label></p>'
        '<p><label>Contact email <input type="email" name="email" '
        'autocomplete="email" required maxlength="254"></label></p>'
        '<p><label>Service <select name="service" required>'
        + _options(tuple(choice for choice in MojPropRequest.ROUTE_CHOICES
                         if choice[0] != "digital"), selected=selected) + '</select></label></p>'
        '<p>For downloadable products, use the verified store checkout; this '
        'form creates only an unpaid manual-review request.</p>'
        '<p><label>Time horizon <select name="horizon" required>'
        + _options(MojPropRequest.HORIZON_CHOICES) + '</select></label></p>'
        '<p><label>Objectives and deliverables <textarea name="notes" '
        'required minlength="20" maxlength="5000" rows="7">' +
        escape(prefill_notes) + '</textarea>'
        '</label></p>'
        '<input type="hidden" name="website" value="">'
        '<input type="hidden" name="idempotency_key" value="' +
        escape(str(uuid4()), quote=True) + '">'
        '<p><label><input type="checkbox" name="consent" value="on" required> '
        'I consent to storing this request for a written manual review.</label></p>'
        '<p><button type="submit">Submit request for manual review</button></p>'
        '</form><p><a href="/moj-prop/">Return to Moj Prop</a></p>'
    )
    return _private_html("Moj Prop request", form, status=status)


def status_form(request, *, error=None, status=200):
    """CSRF-protected POST status lookup: bearer secret never enters a URL."""
    message = ('<p role="alert">' + escape(error) + '</p>') if error else ''
    csrf = escape(get_token(request), quote=True)
    content = (
        '<p>Check an existing manual-review request. Never send a new payment '
        'to check a receipt. Your private token stays in the POST body.</p>'
        + message +
        '<form method="post" action="/moj-prop-status/?format=html" '
        'enctype="application/x-www-form-urlencoded">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrf + '">'
        '<p><label>Private receipt token '
        '<input name="receipt_token" required autocomplete="off" '
        'spellcheck="false" maxlength="256"></label></p>'
        '<p><button type="submit">Check review status</button></p>'
        '</form><p><a href="/moj-prop-intake/?format=html">New request</a></p>'
    )
    return _private_html("Check Moj Prop request", content, status=status)


def status_result(reference, stage):
    """Only a public review-stage label, never identity/payment/delivery proof."""
    body = (
        '<p role="status">Request <strong>' + escape(reference) +
        '</strong>: ' + escape(stage) + '.</p>'
        '<p>This status is not a paid invoice, payment confirmation, '
        'customer acknowledgement or proof of delivery.</p>'
        '<p><a href="/moj-prop-status/?format=html">Check another token</a></p>'
    )
    return _private_html("Review status", body)


def created_receipt(payload, *, reused=False):
    """Return only an allocated request reference and its private bearer token."""
    if (type(payload) is not dict or payload.get("ok") is not True
            or type(payload.get("request_id")) is not str
            or type(payload.get("receipt_token")) is not str):
        raise ValueError("Verified request receipt required")
    reference = escape(payload["request_id"])
    token = escape(payload["receipt_token"])
    body = (
        '<p role="status">' +
        ('The original request was recovered without creating a second lead.'
         if reused else 'Your request was recorded for manual review.') +
        ' No payment was taken. A written proposal is not yet issued.</p>'
        '<p>Request ID: <strong>' + reference + '</strong></p>'
        '<p>Save this private receipt token; it grants access to review status. '
        'Never publish it or send it to strangers.</p>'
        '<pre id="private-receipt">' + token + '</pre>'
        '<p>Review status may be checked through the Moj Prop site. '
        'This receipt is not a tax invoice, a payment confirmation or '
        'proof of delivery.</p>'
        '<p><a href="/moj-prop-status/?format=html">Check this request without JavaScript</a></p>'
        '<p><a href="/moj-prop/">Return to Moj Prop</a></p>'
    )
    return _private_html("Request recovered" if reused else "Request received",
                         body, status=200 if reused else 201)
