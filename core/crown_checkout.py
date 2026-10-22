"""Crown Defender's server-owned checkout entry point.

The public route is intentionally unusable until a separately audited,
mainnet-capable checkout adapter is installed AND all approval gates are true.
A game URL, local storage value or a buyer-submitted TxID cannot enable sales.
"""
from importlib import import_module
from urllib.parse import unquote

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.html import format_html
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

ADAPTER = "services.mpw_crown_mainnet_checkout"
HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


def _adapter():
    if (getattr(settings, "CROWN_STORE_ENABLED", False) is not True
            or getattr(settings, "CROWN_PAYMENT_GATEWAY_APPROVED", False) is not True):
        return None
    try:
        module = import_module(ADAPTER)
        if (not callable(getattr(module, "mainnet_checkout_ready", None))
                or not callable(getattr(module, "start_crown_checkout", None))
                or module.mainnet_checkout_ready() is not True):
            return None
        return module
    except (ImportError, AttributeError, OSError, RuntimeError, ValueError):
        return None


def gateway_ready():
    """Never infer readiness from a configured URL or a seeded catalogue."""
    return _adapter() is not None


def _private(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _unavailable():
    return _private(HttpResponse(
        "Crown Defender: purchases are not yet available. "
        "You can fly all premium designs in free test mode.",
        status=503, content_type="text/plain; charset=utf-8",
    ))


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def crown_cosmetic_checkout(request, product_id):
    if request.get_host().split(":")[0].lower() not in HOSTS:
        raise Http404
    from core.crown_fleet import catalogue
    from core.models import Product

    products = Product.objects.filter(pk=product_id, active=True, product_type="game_cosmetic", currency="USD")
    product = products.first()
    if product is None:
        raise Http404
    item = next((row for row in catalogue()
                 if row["sku"] == (product.metadata or {}).get("crown_sku")), None)
    expected_path = "/store/crown/{}/checkout/".format(product_id)
    if (not item or item["available"] is not True
            or item["checkout"] != expected_path or not gateway_ready()):
        return _unavailable()

    if not request.user.is_authenticated:
        return _private(HttpResponseRedirect(
            "/accounts/login/?next=" + expected_path
        ))

    if request.method == "POST":
        # Only audited server code can reserve an invoice. Do not accept an
        # amount, SKU, recipient, chain network, tx hash or user ID from POST.
        adapter = _adapter()
        if adapter is None:
            return _unavailable()
        try:
            path = adapter.start_crown_checkout(buyer_id=request.user.pk, product_id=product.pk)
        except Exception:
            # Provider failures must never produce a paid order or jet grant.
            return _unavailable()
        if not isinstance(path, str):
            return _unavailable()
        normalized = unquote(path)
        if (not normalized.startswith("/commerce/")
                or normalized.startswith("//") or "\\" in normalized
                or "?" in normalized or "#" in normalized
                or any(part in (".", "..") for part in normalized.split("/"))):
            return _unavailable()
        return _private(HttpResponseRedirect(path))

    token = get_token(request)
    # Price is server-side only. No client-submitted amount influences checkout.
    html = format_html(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Crown Defender · Secure Checkout</title>'
        '<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;'
        'background:radial-gradient(circle at 20% 10%,#163b67,#050b19 65%);'
        'color:#f4f6ff;font:16px system-ui}}main{{width:min(440px,90vw);'
        'padding:36px;border-radius:24px;background:#101b30;'
        'box-shadow:0 15px 80px #0009;border:1px solid #426a88}}'
        'button{{padding:15px 24px;border:0;border-radius:12px;background:#52e2ba;'
        'color:#04131e;font-weight:800;cursor:pointer;width:100%}}'
        'p{{line-height:1.6;color:#b6c8db}}</style>'
        '<main><p>CROWN DEFENDER · FLEET COLLECTION</p>'
        '<h1>{}</h1><p>Permanent cosmetic jet skin · No gameplay advantage.</p>'
        '<h2>{} USD</h2><p>TRON checkout. The jet unlocks only when the'
        ' payment is independently verified on-chain.</p>'
        '<form method="post"><input type="hidden" name="csrfmiddlewaretoken"'
        ' value="{}"><button type="submit">Continue to secure payment</button>'
        '</form><p><a href="/games/crown-defender/" style="color:#8ce9ef">'
        'Return to game</a></p></main></html>',
        product.title, item["price"], token,
    )
    response = _private(HttpResponse(html, content_type="text/html; charset=utf-8"))
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    return response
