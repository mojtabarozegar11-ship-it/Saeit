"""Production guest checkout adapter over MojPlayWin's existing TRX ledger.

Guest buyers receive a unique password-disabled Django principal. Existing
order, invoice, chain-finality, ledger and download code remains authoritative.
The browser gets a signed, secure owner cookie so no account signup is needed.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from django.core import signing
from django.http import Http404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

COOKIE = "mpw_trx_guest_owner"
SALT = "mpw.trx.guest.owner.v1"
COOKIE_AGE = 30 * 86400
COOKIE_PATH = "/commerce/trx-easy/"
MAX_COOKIE = 512
INVOICE_LOCATION = re.compile(r"\A/commerce/trx-easy/invoice/[1-9][0-9]*/\Z")


def _host_ok(request):
    return (request.is_secure() and request.get_host().split(":")[0].lower()
            in ("mojplaywin.com", "www.mojplaywin.com"))


def _read_user(request):
    raw = request.COOKIES.get(COOKIE, "")
    if not isinstance(raw, str) or not 20 < len(raw) <= MAX_COOKIE:
        return None
    try:
        data = signing.loads(raw, salt=SALT, max_age=COOKIE_AGE)
        user_id = data.get("u") if type(data) is dict else None
        if type(user_id) is not int or user_id <= 0:
            return None
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        # A signed guest cookie must never become a staff/admin login, even if
        # a guest principal is later misconfigured in the auth database.
        if (user is None or user.has_usable_password()
                or getattr(user, "is_staff", False)
                or getattr(user, "is_superuser", False)):
            return None
        username = str(getattr(user, get_user_model().USERNAME_FIELD, ""))
        if not username.startswith("mpwguest_"):
            return None
        return user
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        return None


def _rate_limit(request):
    """Bound guest account creation; store only an HMAC-derived IP bucket."""
    from django.conf import settings
    from django.core.cache import cache
    ip = request.META.get("REMOTE_ADDR", "")
    if not ip or len(ip) > 80:
        raise Http404
    hour = int(time.time() // 3600)
    key_material = (str(settings.SECRET_KEY) + ":" + str(hour) + ":" + ip).encode()
    key = "mpw:guest:start:" + hashlib.sha256(key_material).hexdigest()
    try:
        if cache.add(key, 1, timeout=3600):
            return
        count = cache.incr(key)
        if count > 20:
            raise Http404
    except Http404:
        raise
    except Exception as exc:
        raise Http404("Guest checkout rate check unavailable") from exc


def _guest_username(request):
    """Stable per-browser identity for concurrent first POSTs, never the raw CSRF secret."""
    from django.conf import settings
    csrf = request.META.get("CSRF_COOKIE", "")
    # csrf_protect has already validated the request before this function runs.
    if not isinstance(csrf, str) or len(csrf) != 32 or not csrf.isascii() or not csrf.isalnum():
        raise Http404("Open the checkout page before submitting an invoice")
    digest = hmac.new(
        str(settings.SECRET_KEY).encode("utf8"),
        ("mpw:guest:csrf:v2:" + csrf).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()[:40]
    return "mpwguest_" + digest


def _new_user(request):
    """Resolve both simultaneous first orders to one unique password-disabled user."""
    from django.contrib.auth import get_user_model
    from django.db import IntegrityError, transaction

    # The guest principal is the durable owner of the order.  Persist the
    # address submitted by the checkout form before invoice binding; otherwise
    # record_invoice() correctly refuses to create an unowned delivery record.
    submitted_email = _required_checkout_email(request)

    _rate_limit(request)
    Model = get_user_model()
    field = Model.USERNAME_FIELD
    value = _guest_username(request)
    if field.lower() in ("email", "email_address"):
        value += "@guest.mojplaywin.com"
    if not Model._meta.get_field(field).unique:
        raise Http404("Guest identity field must be unique")
    query = {field: value}
    user = Model.objects.filter(**query).first()
    if user is None:
        try:
            # The auth username/email field must retain its database uniqueness.
            # If another request wins this insert, its committed user is reused.
            with transaction.atomic():
                user = Model(**query)
                user.set_unusable_password()
                if hasattr(user, "is_active"):
                    user.is_active = True
                # Never inherit a customized user model's privileged defaults.
                for privileged_flag in ("is_staff", "is_superuser"):
                    if hasattr(user, privileged_flag):
                        setattr(user, privileged_flag, False)
                user.save(force_insert=True)
        except IntegrityError:
            user = Model.objects.filter(**query).first()
            if user is None:
                raise
    if (not getattr(user, "is_active", True) or user.has_usable_password()
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)):
        raise Http404("Guest identity conflict")
    if hasattr(user, "email"):
        existing_email = str(getattr(user, "email", "") or "").strip().lower()
        if existing_email and existing_email != submitted_email:
            raise Http404("Guest email identity mismatch")
        if not existing_email:
            user.email = submitted_email
            user.save(update_fields=["email"])
    token = signing.dumps({"u": int(user.pk), "n": secrets.token_urlsafe(24)}, salt=SALT)
    if len(token) > MAX_COOKIE:
        raise Http404("Guest receipt could not be issued")
    return user, token


def _bind_guest_email(request, user):
    """Bind a submitted address only to this existing guest principal."""
    submitted_email = _required_checkout_email(request)
    existing_email = str(getattr(user, "email", "") or "").strip().lower()
    if existing_email and existing_email != submitted_email:
        raise Http404("Guest email identity mismatch")
    if not existing_email and hasattr(user, "email"):
        user.email = submitted_email
        user.save(update_fields=["email"])
    return user


def _required_checkout_email(request):
    """Every invoice POST, including signed-in checkout, must carry one valid email."""
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    values = []
    for key in ("email", "buyer_email", "customer_email", "purchase_email", "purchaser_email"):
        for raw in request.POST.getlist(key):
            address = str(raw).strip().casefold()
            if not address:
                continue
            if len(address) > 254:
                raise Http404("Valid purchase email required")
            try:
                validate_email(address)
            except ValidationError as exc:
                raise Http404("Valid purchase email required") from exc
            values.append(address)
    if not values or any(value != values[0] for value in values):
        raise Http404("Missing or conflicting purchase email")
    return values[0]


def _identity(request, *, create=False):
    if not _host_ok(request):
        raise Http404
    # A browser's required HTML field cannot protect direct POST requests.
    checkout_email = _required_checkout_email(request) if create else None
    current = getattr(request, "user", None)
    if current is not None and getattr(current, "is_authenticated", False):
        if create and str(getattr(current, "email", "") or "").strip().casefold() != checkout_email:
            raise Http404("Account email must match purchase email")
        return current, None
    user = _read_user(request)
    token = None
    if user is None and create:
        user, token = _new_user(request)
    elif user is not None and create:
        # _read_user already checked the signed guest identity.  A custom
        # Django user model may use email, not username, as USERNAME_FIELD.
        user = _bind_guest_email(request, user)
    if user is None:
        raise Http404("Guest purchase session missing or expired")
    return user, token


def _install_cookie(response, token):
    # Personalized purchase pages must vary on Cookie, including existing sessions.
    from django.utils.cache import patch_vary_headers
    patch_vary_headers(response, ("Cookie",))
    if token:
        response.set_cookie(COOKIE, token, max_age=COOKIE_AGE, path=COOKIE_PATH,
                            secure=True, httponly=True, samesite="Lax")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "same-origin"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _dispatch(request, view, args, kwargs, *, create=False):
    if create:
        from django.conf import settings
        # Capturing immutable checkout ownership is independent of opening
        # public recovery routes or approving outbound recovery mail.
        if (getattr(settings, "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED", False) is True
                or getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True):
            from services.mpw_trx_email_recovery import bound_checkout
            response = bound_checkout(request, view, _identity, _install_cookie, args, kwargs)
            if _is_invoice_redirect(response):
                _count_checkout_event(request, "order_start_accepted", args, kwargs)
            return response
    user, token = _identity(request, create=create)
    request.user = user
    response = view(request, *args, **kwargs)
    response = _install_cookie(response, token)
    if create and _is_invoice_redirect(response):
        _count_checkout_event(request, "order_start_accepted", args, kwargs)
    return response


def _is_invoice_redirect(response):
    """Only an issued invoice counts as an accepted checkout.

    Validation pages (HTTP 200) and redirects back to the store (HTTP 302)
    are not new invoices.  No payment or buyer details are inspected here.
    """
    location = response.get("Location", "")
    return (getattr(response, "status_code", None) in (302, 303)
            and isinstance(location, str)
            and INVOICE_LOCATION.fullmatch(location) is not None)


def _count_checkout_event(request, stage, args=(), kwargs=None):
    """Never change the outcome of any purchase/receipt handler."""
    try:
        from services.mpw_checkout_funnel import record
        product_id = (kwargs or {}).get("product_id", args[0] if args else 0)
        record(request, stage, product_id)
    except Exception:
        pass


def _checkout_page(request, product_id, pages_namespace):
    from django.conf import settings
    from django.db import connection
    from django.shortcuts import render
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from services.mpw_trx_commercial_context import rights_cleared_for_sale
    from services.mpw_trx_commercial_web import _configured_receiver, _nocache
    from services.mpw_walletless_commercial_intent import _commercial_db

    if not _host_ok(request) or type(product_id) is not int:
        raise Http404
    try:
        _commercial_db(settings, connection)
        _configured_receiver()
    except Exception as exc:
        from services.mpw_trx_walletless_core import PaymentHold
        if isinstance(exc, PaymentHold):
            raise Http404("TRX checkout is temporarily unavailable") from exc
        raise
    if product_id not in getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ()):
        raise Http404
    product = Product.objects.select_related("knowledge_article").filter(
        pk=product_id, active=True).first()
    if product is None or not _eligible(product) or not rights_cleared_for_sale(product):
        raise Http404
    response = _nocache(render(request, "mpw_commerce/product_checkout.html", {
        "product": product, "price_usd": format(product.price, ".2f"),
        "mpw_trx_easy_enabled": True, "mpw_guest_checkout": True,
    }))
    response = pages_namespace["_checkout_csrf_referrer"](response)
    response["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "script-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
    response["X-Robots-Tag"] = "noindex, nofollow"
    _count_checkout_event(request, "checkout_view", (product_id,))
    return response


def patch_public(namespace):
    from django.views.decorators.cache import never_cache
    from django.views.decorators.http import require_GET

    old_checkout = namespace.get("product_checkout")
    old_purchases = namespace.get("purchases")
    if old_checkout is None or old_purchases is None:
        raise RuntimeError("Expected buyer routes are missing")

    def product_checkout(request, product_id):
        return _checkout_page(request, product_id, namespace)

    @never_cache
    @require_GET
    def purchases(request):
        # Missing or expired owner cookie is a recoverable browser state, not a missing URL.
        if not _host_ok(request):
            raise Http404
        current = getattr(request, "user", None)
        authenticated = bool(current is not None and getattr(current, "is_authenticated", False))
        if not authenticated and _read_user(request) is None:
            from django.http import HttpResponse
            from django.conf import settings
            recovery_link = (
                '<p><a href="/commerce/trx-easy/recover/">Recover using purchase email</a></p>'
                if (getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True
                    and getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is True)
                else ""
            )
            response = HttpResponse(
                '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>Purchase recovery | MojPlayWin</title></head><body>'
                '<main><h1>TRX purchase recovery</h1>'
                '<p>No active purchase session was found in this browser. '
                'Your orders are private and require the original browser session.</p>'
                '<p>If you already paid, do not pay again. Contact purchase support '
                'with your invoice reference and transaction hash. '
                'Never share a wallet recovery phrase or private key.</p>'
                + recovery_link +
                '<p><a href="/store/">Return to store</a> | '
                '<a href="mailto:support@mojplaywin.com">Purchase support</a></p>'
                '</main></body></html>',
                content_type="text/html; charset=utf-8",
                status=200,
            )
            response["Content-Security-Policy"] = (
                "default-src 'none'; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'none'")
            return _install_cookie(response, None)
        # Preserve the original view decorators and permission checks.
        return _dispatch(request, old_purchases, (), {})

    namespace["product_checkout"] = never_cache(require_GET(product_checkout))
    namespace["purchases"] = purchases


def patch_commercial(namespace):
    if namespace.get("_mpw_guest_checkout_installed") is True:
        return
    from django.views.decorators.cache import never_cache
    from django.views.decorators.csrf import csrf_protect
    from django.views.decorators.http import require_GET, require_POST
    targets = {
        "start_order": ("_start_order", True, require_POST, True),
        "show_invoice": ("_show_invoice", False, require_GET, False),
        "invoice_status": ("_invoice_status", False, require_GET, False),
        "reconcile_invoice": ("_reconcile_invoice", False, require_POST, True),
        "download_paid": ("_download_paid", False, require_GET, False),
    }
    for public_name, (inner_name, create, method_decorator, csrf) in targets.items():
        inner = namespace.get(inner_name)
        if inner is None:
            raise RuntimeError("Expected TRX handler missing: " + inner_name)

        def make_view(view, make_claim, view_name):
            def wrapped(request, *args, **kwargs):
                response = _dispatch(request, view, args, kwargs, create=make_claim)
                if view_name in ("show_invoice", "download_paid") and \
                        getattr(response, "status_code", 500) == 200:
                    event = "invoice_view" if view_name == "show_invoice" else "paid_download"
                    _count_checkout_event(request, event)
                return response
            wrapped.__name__ = view_name
            return never_cache(csrf_protect(method_decorator(wrapped)) if csrf
                               else method_decorator(wrapped))
        namespace[public_name] = make_view(inner, create, public_name)
    patterns = namespace.get("COMMERCIAL_URLPATTERNS")
    if isinstance(patterns, tuple):
        rebuilt = []
        route_names = (
            ("/start/", "start_order"), ("/invoice/", "show_invoice"),
            ("/status/", "invoice_status"), ("/reconcile/", "reconcile_invoice"),
            ("/download/", "download_paid"),
        )
        for route, view in patterns:
            route_name = next((name for token, name in route_names if token in route), None)
            replacement = namespace.get(route_name, view)
            rebuilt.append((route, replacement))
        from django.conf import settings
        if getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True:
            from services.mpw_trx_email_recovery import (
                recovery_request, recovery_verify, recovery_orders, recovery_download,
            )
            extra = (
                ("commerce/trx-easy/recover/", recovery_request),
                ("commerce/trx-easy/recover/verify/", recovery_verify),
                ("commerce/trx-easy/recover/orders/", recovery_orders),
                ("commerce/trx-easy/recover/download/<int:invoice_id>/", recovery_download),
            )
            existing = {route for route, _ in rebuilt}
            if any(route in existing for route, _ in extra):
                raise RuntimeError("Recovery URL collision")
            rebuilt.extend(extra)
        namespace["COMMERCIAL_URLPATTERNS"] = tuple(rebuilt)
    namespace["_mpw_guest_checkout_installed"] = True
