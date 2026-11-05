"""Email-only recovery for paid MojPlayWin guest TRX orders.

Install only after core migration 0040 and the corresponding URL/checkout
adapter release have passed preflight.  Outbound mail is independently gated
by MPW_GUEST_RECOVERY_EMAIL_APPROVED, which defaults to False.

Legacy orders without a per-order email claim are deliberately excluded.
No request changes a payment, payment ledger, fulfillment, or old order owner.
"""
from __future__ import annotations

from contextvars import ContextVar
import hashlib
import hmac
from importlib import import_module
import logging
import re
import secrets
from datetime import timedelta
from html import escape

from django.apps import apps
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.db.models.signals import post_save
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from core.models import (
    GuestOrderEmail, GuestRecoveryRate, GuestRecoveryToken,
    Order, OrderItem, PaymentIntent,
)
from core.crown_tron_receipts import PROVIDER, verified_walletless_credit


LOG = logging.getLogger("mpw.guest_recovery")
_CHECKOUT_SIGNAL_SCOPE = ContextVar("mpw_checkout_signal_scope", default=None)
ROOT = "/commerce/trx-easy/recover/"
SESSION_COOKIE = "mpw_recovery_scope"
SESSION_SALT = "mpw.guest.recovery.scope.v1"
SESSION_AGE = 15 * 60
CODE_LENGTH = 43  # secrets.token_urlsafe(32), 256 bits
INVOICE_RE = re.compile(r"\A/commerce/trx-easy/invoice/([1-9][0-9]*)/\Z")
GENERIC = "If eligible paid orders exist for that address, recovery instructions will be sent."


def _host(request):
    return request.is_secure() and request.get_host().split(":")[0].lower() in (
        "mojplaywin.com", "www.mojplaywin.com"
    )


def _email(value):
    if not isinstance(value, str) or len(value) > 254 or "\n" in value or "\r" in value:
        raise ValueError("Invalid email")
    value = value.strip().casefold()
    try:
        validate_email(value)
    except ValidationError as exc:
        raise ValueError("Invalid email") from exc
    return value


def _posted_email(request):
    # Different checkout templates have historically used these four names.
    # Reject conflicting values instead of choosing an attacker-controlled one.
    values = []
    for key in ("email", "buyer_email", "customer_email", "purchase_email"):
        for value in request.POST.getlist(key):
            if value:
                values.append(_email(value))
    if not values or any(value != values[0] for value in values):
        raise ValueError("Missing or conflicting checkout email")
    return values[0]


def _digest(value, purpose="email"):
    return hmac.new(
        str(settings.SECRET_KEY).encode("utf-8"),
        ("mpw:recovery:" + purpose + ":" + value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _private(response):
    patch_vary_headers(response, ("Cookie",))
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Content-Security-Policy"] = (
        "default-src 'none'; form-action 'self'; base-uri 'none'; "
        "frame-ancestors 'none'"
    )
    return response


def _page(title, body, request=None, *, status=200):
    markup = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>" + escape(title) + " | MojPlayWin</title></head>"
        '<body><main><h1>' + escape(title) + "</h1>" + body +
        '<p><a href="/store/">Return to store</a></p></main></body></html>'
    )
    return _private(HttpResponse(markup, status=status, content_type="text/html; charset=utf-8"))


def _form(request, action, fields, button):
    fields_html = "".join(
        '<p><label>' + escape(label) + ' <input name="' + escape(name) +
        '" type="' + escape(kind) + '" autocomplete="off" required' +
        (' maxlength="254"' if kind == "email" else ' maxlength="43"') +
        '></label></p>'
        for label, name, kind in fields
    )
    return (
        '<form method="post" action="' + escape(action) + '">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="' +
        escape(get_token(request)) + '">' + fields_html +
        '<button type="submit">' + escape(button) + '</button></form>'
    )


def _guest(order):
    user = order.customer
    username = str(getattr(user, "username", ""))
    return (
        username.startswith("mpwguest_") and user.is_active and
        not user.is_staff and not user.is_superuser and
        not user.has_usable_password()
    )


def _ready(order):
    """All items must be ready, not merely one item or a paid flag."""
    Fulfillment = apps.get_model("mpw_commerce", "CommerceFulfillment")
    fields = {f.name: f for f in Fulfillment._meta.fields}
    item = fields.get("item")
    if (item is None or getattr(getattr(item, "related_model", None), "_meta", None)
            is None or item.related_model._meta.label_lower != "core.orderitem"
            or "status" not in fields):
        return False
    count = OrderItem.objects.filter(order_id=order.pk).count()
    if count < 1:
        return False
    return Fulfillment.objects.filter(
        item__order_id=order.pk, status__iexact="ready"
    ).count() == count


def _eligible_orders(email_digest):
    """Recheck settled chain proof and delivery on every access."""
    claims = GuestOrderEmail.objects.filter(email_digest=email_digest).select_related(
        "order__customer"
    ).order_by("-order__created_at")[:100]
    results = []
    for claim in claims:
        order = claim.order
        if not _guest(order):
            continue
        intent = PaymentIntent.objects.filter(order_id=order.pk, provider=PROVIDER).first()
        if intent is None or not verified_walletless_credit(order, intent) or not _ready(order):
            continue
        results.append((order, intent))
    return results


def _bucket_allowed(value, *, purpose, limit):
    key = _digest(value, purpose)
    try:
        with transaction.atomic():
            now = timezone.now()
            row, _ = GuestRecoveryRate.objects.select_for_update().get_or_create(
                bucket=key,
                defaults={"expires_at": now + timedelta(hours=1)},
            )
            if row.expires_at <= now:
                row.count = 0
                row.expires_at = now + timedelta(hours=1)
            row.count += 1
            row.save(update_fields=["count", "expires_at"])
            return row.count <= limit
    except Exception:  # unavailable storage must fail closed
        LOG.warning("mpw_recovery_rate_limit_unavailable")
        return False


def _allowed(request, email=None, *, verify=False):
    ip = request.META.get("REMOTE_ADDR", "")
    if not isinstance(ip, str) or not ip or len(ip) > 80:
        return False
    hour = str(int(timezone.now().timestamp() // 3600))
    if not _bucket_allowed(hour + ":" + ip, purpose="ip", limit=12 if verify else 8):
        return False
    if email and not _bucket_allowed(hour + ":" + email, purpose="email", limit=3):
        return False
    return True


def _issue(email, email_digest):
    # No plaintext token is placed in a table, query string or URL path.
    code = secrets.token_urlsafe(32)
    row = GuestRecoveryToken.objects.create(
        token_digest=hashlib.sha256(code.encode("ascii")).hexdigest(),
        email_digest=email_digest,
        expires_at=timezone.now() + timedelta(minutes=15),
    )
    try:
        EmailMessage(
            subject="MojPlayWin purchase recovery code",
            body=("A purchase-recovery code was requested for your MojPlayWin orders.\n\n"
                  "Open https://mojplaywin.com" + ROOT + "verify/ and enter:\n\n"
                  + code + "\n\nExpires in 15 minutes; use once. "
                  "If this was not you, ignore this message. Never share a wallet seed phrase."),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        ).send(fail_silently=False)
    except Exception:
        row.delete()
        LOG.warning("mpw_recovery_delivery_unavailable")
    else:
        LOG.info("mpw_recovery_instruction_issued")


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def recovery_request(request):
    if not _host(request):
        raise Http404
    if getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is not True:
        return _page("Email recovery is not yet available",
                     '<p>Do not make another payment. If you already paid, '
                     'contact <a href="mailto:support@mojplaywin.com">purchase support</a> '
                     'with your invoice reference and transaction hash. '
                     'Never share a wallet recovery phrase.</p>')
    if request.method == "GET":
        return _page("Recover a TRX purchase", '<p>Use the email entered at checkout.</p>' +
                     _form(request, ROOT, [("Purchase email", "email", "email")], "Request code"), request)
    try:
        address = _email(request.POST.get("email", ""))
    except ValueError:
        address = None
    if address and _allowed(request, address):
        digest = _digest(address)
        try:
            orders = _eligible_orders(digest)
        except Exception:
            # An outage must neither disclose email existence nor send a code.
            LOG.warning("mpw_recovery_eligibility_unavailable")
            orders = []
        if orders:
            # Every eligible claim is immutable and was captured at checkout.
            _issue(orders[0][0].guest_email_claim.email_address, digest)
    LOG.info("mpw_recovery_request_received")
    return _page("Check your email", "<p>" + escape(GENERIC) + "</p>")


def _consume(code):
    if not isinstance(code, str) or len(code) != CODE_LENGTH or not re.fullmatch(r"[A-Za-z0-9_-]{43}", code):
        return None
    digest = hashlib.sha256(code.encode("ascii")).hexdigest()
    with transaction.atomic():
        row = GuestRecoveryToken.objects.select_for_update().filter(token_digest=digest).first()
        now = timezone.now()
        if row is None or row.consumed_at is not None or row.expires_at <= now:
            return None
        row.consumed_at = now
        row.save(update_fields=["consumed_at"])
        return row.email_digest


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def recovery_verify(request):
    if not _host(request):
        raise Http404
    if request.method == "GET":
        return _page("Enter recovery code", _form(request, ROOT + "verify/",
                     [("Code from email", "code", "text")], "Verify"), request)
    if not _allowed(request, verify=True):
        return _page("Recovery unavailable", "<p>Please try again later.</p>", status=429)
    digest = _consume(request.POST.get("code", ""))
    if digest is None:
        LOG.info("mpw_recovery_code_rejected")
        return _page("Recovery unavailable", "<p>Invalid or expired code.</p>", status=400)
    response = redirect(ROOT + "orders/")
    response.set_cookie(
        SESSION_COOKIE,
        signing.dumps({"e": digest, "n": secrets.token_urlsafe(16)}, salt=SESSION_SALT),
        max_age=SESSION_AGE, path=ROOT, secure=True, httponly=True, samesite="Lax",
    )
    LOG.info("mpw_recovery_code_consumed")
    return _private(response)


def _scope(request):
    raw = request.COOKIES.get(SESSION_COOKIE, "")
    if not isinstance(raw, str) or len(raw) > 512:
        raise Http404
    try:
        data = signing.loads(raw, salt=SESSION_SALT, max_age=SESSION_AGE)
        digest = data.get("e") if type(data) is dict else None
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise Http404
        return digest
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        raise Http404


@never_cache
@require_GET
def recovery_orders(request):
    if not _host(request):
        raise Http404
    orders = _eligible_orders(_scope(request))
    if not orders:
        return _page("No downloadable purchases", "<p>No qualifying paid downloads were found.</p>")
    links = "".join(
        '<li>Order ' + str(order.pk) + ': <a href="' + ROOT + "download/" +
        str(intent.pk) + '/">Download verified purchase</a></li>'
        for order, intent in orders
    )
    return _page("Your paid purchases", "<ul>" + links + "</ul>")


@never_cache
@require_GET
def recovery_download(request, invoice_id):
    if not _host(request) or type(invoice_id) is not int or invoice_id <= 0:
        raise Http404
    digest = _scope(request)
    intent = PaymentIntent.objects.select_related("order__customer").filter(pk=invoice_id).first()
    if intent is None:
        raise Http404
    order = intent.order
    claim = GuestOrderEmail.objects.filter(order=order, email_digest=digest).first()
    if claim is None or not _guest(order) or not verified_walletless_credit(order, intent) or not _ready(order):
        raise Http404
    # The public download URL has a guest-cookie adapter around the original
    # handler. Sending a recovered buyer through that adapter would discard
    # this independently verified identity and demand the lost cookie again.
    # Invoke only the existing private delivery handler, after the recovery
    # claim/finality/fulfillment checks above. The handler retains its own
    # order-owner and protected-file authorization checks.
    try:
        delivery = getattr(import_module("services.mpw_trx_commercial_web"),
                           "_download_paid", None)
    except ImportError:
        delivery = None
    if not callable(delivery):
        LOG.error("mpw_recovery_private_delivery_unavailable")
        raise Http404
    request.user = order.customer
    response = delivery(request, invoice_id=invoice_id)
    LOG.info("mpw_recovery_download_delegated")
    return _private(response)


def bound_checkout(request, view, identity, install_cookie, args, kwargs):
    """Attach email only to a new order created in this exact checkout POST.

    A reused order may proceed only if it already bears the *same* claim.
    Never infer ownership of older orders from a mutable auth.User.email.
    """
    if not _host(request):
        raise Http404
    try:
        email = _posted_email(request)
    except ValueError:
        return _private(HttpResponseBadRequest("A valid purchase email is required."))
    digest = _digest(email)
    captured = []
    with transaction.atomic():
        user, cookie = identity(request, create=True)
        request.user = user
        # Registered-account checkout is governed by its original auth path.
        if user.has_usable_password():
            response = view(request, *args, **kwargs)
            return install_cookie(response, cookie)

        scope = object()

        def record_order(sender, instance, created, **unused):
            # Django signals are process-global. Ignore events emitted by
            # other concurrent checkout requests, even for the same guest.
            if _CHECKOUT_SIGNAL_SCOPE.get() is not scope or not created:
                return
            if instance.customer_id != user.pk:
                raise ValueError("TRX checkout did not retain guest owner")
            GuestOrderEmail.objects.create(
                order=instance, email_address=email, email_digest=digest,
            )
            captured.append(instance.pk)

        signal_id = ("mpw_guest_checkout_email", id(request))
        scope_token = _CHECKOUT_SIGNAL_SCOPE.set(scope)
        try:
            post_save.connect(record_order, sender=Order, weak=False, dispatch_uid=signal_id)
            response = view(request, *args, **kwargs)
        finally:
            try:
                post_save.disconnect(sender=Order, dispatch_uid=signal_id)
            finally:
                _CHECKOUT_SIGNAL_SCOPE.reset(scope_token)

        match = INVOICE_RE.fullmatch(response.get("Location", "")) if response.status_code in (302, 303) else None
        if match is not None:
            intent = PaymentIntent.objects.select_related("order").filter(pk=int(match.group(1))).first()
            claim = (GuestOrderEmail.objects.filter(order_id=intent.order_id).first()
                     if intent is not None else None)
            if (intent is None or intent.order.customer_id != user.pk or
                    claim is None or not hmac.compare_digest(claim.email_digest, digest) or
                    _email(claim.email_address) != email):
                raise Http404("Checkout email ownership binding unavailable")
        elif captured:
            # Never leave an orphan claim/order from an unsuccessful checkout.
            raise Http404("Checkout did not return its invoice")
    return install_cookie(response, cookie)
