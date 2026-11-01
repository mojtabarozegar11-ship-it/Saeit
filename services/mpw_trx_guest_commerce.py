"""Production guest checkout adapter over MojPlayWin's existing TRX ledger.

Guest buyers receive a unique password-disabled Django principal. Existing
order, invoice, chain-finality, ledger and download code remains authoritative.
The browser gets a signed, secure owner cookie so no account signup is needed.
"""
from __future__ import annotations

import hashlib
import hmac
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
        if user is None or user.has_usable_password():
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
                user.save(force_insert=True)
        except IntegrityError:
            user = Model.objects.filter(**query).first()
            if user is None:
                raise
    if not getattr(user, "is_active", True) or user.has_usable_password():
        raise Http404("Guest identity conflict")
    token = signing.dumps({"u": int(user.pk), "n": secrets.token_urlsafe(24)}, salt=SALT)
    if len(token) > MAX_COOKIE:
        raise Http404("Guest receipt could not be issued")
    return user, token


def _identity(request, *, create=False):
    if not _host_ok(request):
        raise Http404
    current = getattr(request, "user", None)
    if current is not None and getattr(current, "is_authenticated", False):
        return current, None
    user = _read_user(request)
    token = None
    if user is None and create:
        user, token = _new_user(request)
    if user is None:
        raise Http404("Guest purchase session missing or expired")
    return user, token


def _install_cookie(response, token):
    # All purchase responses are personalized by a signed guest cookie or login.
    # Preserve pre-existing Vary values even when no new cookie is issued.
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
    user, token = _identity(request, create=create)
    request.user = user
    response = view(request, *args, **kwargs)
    return _install_cookie(response, token)



def _public_price_ok(value):
    """Only real public products at or above the owner-approved USD $4 floor."""
    from decimal import Decimal, InvalidOperation
    if isinstance(value, bool):
        return False
    try:
        amount = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return False
    return amount.is_finite() and amount >= Decimal("4.00")


def _public_shop_page(request, pages_namespace):
    """Guest-only public catalog; diagnostics never become payable public SKUs."""
    if not _host_ok(request):
        raise Http404
    from html import escape
    from types import SimpleNamespace
    from django.conf import settings
    from django.db import connection
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file
    from services.mpw_trx_commercial_context import rights_cleared_for_sale
    from services.mpw_trx_commercial_web import _configured_receiver
    from services.mpw_trx_walletless_core import PaymentHold
    from services.mpw_walletless_commercial_intent import _commercial_db

    try:
        _commercial_db(settings, connection)
        _configured_receiver()
    except PaymentHold as exc:
        raise Http404("TRX catalog temporarily unavailable") from exc

    cards = []
    ids = getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ())
    for product in Product.objects.filter(pk__in=ids, active=True).order_by("pk"):
        if (not _public_price_ok(product.price) or not _eligible(product)
                or not rights_cleared_for_sale(product)):
            continue
        try:
            file = _private_file(SimpleNamespace(product=product))
            if file.is_symlink() or not file.is_file() or file.stat().st_size <= 0:
                continue
        except (OSError, ValueError):
            continue
        cards.append(
            f'<article><h2>{escape(product.title)}</h2>'
            f'<p>${escape(str(product.price))} USD · Pay the quoted amount in TRX</p>'
            f'<a class="button" href="/store/product/{product.pk}/checkout/">'
            'Buy with TRX</a></article>'
        )
    intro = (
        "<p>No account is required. Create your invoice, then pay the exact "
        "quoted TRX amount using Trust Wallet on the TRON network. "
        "Keep this browser to retrieve your purchase. If you already paid "
        "and cannot see your receipt, do not pay again; contact "
        '<a href="mailto:support@mojplaywin.com">purchase support</a>.</p>'
    )
    return pages_namespace["_page"](
        "Buy digital products with TRX",
        intro + "".join(cards) if cards else
        "<p>No products are currently cleared for TRX checkout.</p>"
    )


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
    if (product is None or not _public_price_ok(product.price)
            or not _eligible(product) or not rights_cleared_for_sale(product)):
        raise Http404
    # Direct checkout URLs must meet the same private-deliverable gate as
    # catalog cards; never invite payment for a missing or empty ZIP.
    from types import SimpleNamespace
    from mpw_commerce.downloads import _private_file
    try:
        deliverable = _private_file(SimpleNamespace(product=product))
        if (deliverable.is_symlink() or not deliverable.is_file()
                or deliverable.stat().st_size <= 0):
            raise Http404("Product delivery is unavailable")
    except (OSError, ValueError) as exc:
        raise Http404("Product delivery is unavailable") from exc
    response = _nocache(render(request, "mpw_commerce/product_checkout.html", {
        "product": product, "price_usd": format(product.price, ".2f"),
        "mpw_trx_easy_enabled": True, "mpw_guest_checkout": True,
    }))
    response = pages_namespace["_checkout_csrf_referrer"](response)
    response["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "script-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
    response["X-Robots-Tag"] = "noindex, nofollow"
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
        # A missing/expired guest owner cookie is not a missing URL.
        # Never reveal orders without a signed cookie or authenticated user.
        if not _host_ok(request):
            raise Http404
        current = getattr(request, "user", None)
        authenticated = bool(current is not None and getattr(current, "is_authenticated", False))
        if not authenticated and _read_user(request) is None:
            from django.http import HttpResponse
            response = HttpResponse(
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                "<title>TRX purchase recovery | MojPlayWin</title></head><body>"
                "<main><h1>TRX purchase recovery</h1>"
                "<p>No active purchase session was found in this browser. "
                "For security, purchases cannot be displayed without the original "
                "browser session.</p>"
                "<p>If you have already paid, do not send another payment. "
                "Contact purchase support with your invoice reference and "
                "transaction hash; never send a wallet recovery phrase.</p>"
                "<p><a href=\"/store/\">Return to store</a> "
                "<a href=\"mailto:support@mojplaywin.com\">Purchase support</a></p></main></body></html>",
                content_type="text/html; charset=utf-8",
                status=200,
            )
            response["Content-Security-Policy"] = (
                "default-src 'none'; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'none'")
            return _install_cookie(response, None)
        # Keep the original authentication, permission and cache decorators.
        # _dispatch installs the verified guest principal before they run.
        return _dispatch(request, old_purchases, (), {})

    namespace["product_checkout"] = never_cache(require_GET(product_checkout))
    if callable(namespace.get("public_shop")) and callable(namespace.get("_page")):
        def public_shop(request):
            return _public_shop_page(request, namespace)
        namespace["public_shop"] = never_cache(require_GET(public_shop))
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
                return _dispatch(request, view, args, kwargs, create=make_claim)
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
        namespace["COMMERCIAL_URLPATTERNS"] = tuple(rebuilt)
    namespace["_mpw_guest_checkout_installed"] = True
