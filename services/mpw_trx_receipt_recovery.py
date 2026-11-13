"""Email-free TRX guest purchase recovery with an invoice-scoped receipt key.

The key is an unguessable, Django-signed bearer credential, never a proof of
payment. Possession authorizes access to ONE existing invoice only; the
unchanged server-side paid-file handler still checks blockchain settlement,
order ownership, approved artifacts, and private file safety.

No mail, wallet login, database migration, or external payment is involved.
"""
from __future__ import annotations

from html import escape

from django.core import signing
from django.http import Http404, HttpResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

RECEIPT_SALT = "mpw.trx.guest.invoice.receipt.v1"
RECEIPT_PATH = "/commerce/trx-easy/receipt/"
MAX_RECEIPT_LENGTH = 512


def _guest_principal(user):
    from django.contrib.auth import get_user_model

    field = get_user_model().USERNAME_FIELD
    return (user is not None and getattr(user, "is_active", False) is True
            and not user.has_usable_password()
            and str(getattr(user, field, "")).startswith("mpwguest_"))


def issue_receipt(invoice_id, user):
    """Issue only for a known guest owner; call after invoice ownership check."""
    if (type(invoice_id) is not int or invoice_id <= 0
            or not _guest_principal(user)
            or type(user.pk) is not int or user.pk <= 0):
        raise Http404("Receipt not available for this buyer")
    code = signing.dumps({"v": 1, "i": invoice_id, "u": user.pk}, salt=RECEIPT_SALT)
    if len(code) > MAX_RECEIPT_LENGTH:
        raise Http404("Receipt cannot be issued")
    return code


def _read_receipt(raw):
    if not isinstance(raw, str) or not 20 < len(raw) <= MAX_RECEIPT_LENGTH:
        raise Http404("Invalid receipt key")
    try:
        claim = signing.loads(raw, salt=RECEIPT_SALT)
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError) as exc:
        raise Http404("Invalid receipt key") from exc
    if (type(claim) is not dict or set(claim) != {"v", "i", "u"}
            or type(claim["v"]) is not int or claim["v"] != 1
            or type(claim["i"]) is not int or claim["i"] <= 0
            or type(claim["u"]) is not int or claim["u"] <= 0):
        raise Http404("Invalid receipt key")
    return claim["i"], claim["u"]


def receipt_markup(invoice_id, user):
    """Personalized invoice content; never insert this into public catalog pages."""
    if not _guest_principal(user):
        return ""
    code = escape(issue_receipt(invoice_id, user))
    return (
        '<section aria-label="Private purchase receipt">'
        '<h2>Keep your private receipt key</h2>'
        '<p>No email or account is required. Save this key before closing the '
        'page. It restores this invoice\'s verified digital download if you '
        'lose access to this browser. Anyone holding the key can claim this '
        'purchase; never share it publicly.</p>'
        '<label for="mpw-receipt-key">Your private purchase receipt key</label>'
        '<textarea id="mpw-receipt-key" rows="4" readonly>' + code + '</textarea>'
        '<p><a href="' + RECEIPT_PATH + '">Recover a purchase using its key</a></p>'
        '</section>'
    )


def _page(request, text, *, status=200):
    token = escape(get_token(request), quote=True)
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        '<title>Recover TRX download | MojPlayWin</title></head><body>'
        '<main><h1>Recover a TRX download</h1>'
        '<p>No email is required. Enter the private receipt key saved '
        'from your invoice; it can only restore that same purchase.</p>'
        '<p>' + escape(text) + '</p>'
        '<form method="post" action="' + RECEIPT_PATH + '">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="' + token + '">'
        '<label for="receipt">Private receipt key</label>'
        '<textarea id="receipt" name="receipt" maxlength="512" rows="4" required>'
        '</textarea><button type="submit">Retrieve verified download</button>'
        '</form><p>Never pay twice. Contact purchase support if you lost the key '
        'and have an invoice reference and transaction hash.</p>'
        '<a href="/commerce/trx-easy/">Back to store</a></main></body></html>'
    )
    response = HttpResponse(html, status=status, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "no-referrer"
    response["Content-Security-Policy"] = (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def receipt_recovery(request):
    from core.models import PaymentIntent
    from services.mpw_trx_guest_commerce import _host_ok
    from services.mpw_trx_commercial_web import _download_paid
    from services.mpw_walletless_commercial_intent import PROVIDER

    if not _host_ok(request):
        raise Http404
    if request.method == "GET":
        return _page(request, "Keep your key private.")
    invoice_id, owner_id = _read_receipt(request.POST.get("receipt", ""))
    intent = PaymentIntent.objects.select_related("order__customer").filter(
        pk=invoice_id, provider=PROVIDER, order__customer_id=owner_id,
    ).first()
    if intent is None or not _guest_principal(intent.order.customer):
        raise Http404("Receipt has no matching private purchase")
    # This scoped request never establishes the broad guest-owner cookie.
    # Paid-file authorization is performed anew on every download.
    request.user = intent.order.customer
    response = _download_paid(request, invoice_id)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
