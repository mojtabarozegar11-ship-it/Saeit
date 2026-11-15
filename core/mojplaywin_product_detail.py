"""Canonical MojPlayWin catalog detail pages for the three existing store cards.

These records mirror the public store's declared descriptions. The presence
of a product page is NOT proof of license, inventory, TRX checkout or delivery.
Zomorod Melal product SEO stays on its existing view and separate host.
"""
from decimal import Decimal

from django.http import Http404
from django.shortcuts import render
from django.db import DatabaseError
import logging

from .product_seo_views import product_detail as zomorod_product_detail
from .models import Product

MPW_HOSTS = frozenset({"mojplaywin.com", "www.mojplaywin.com"})
ZOMOROD_HOSTS = frozenset({"zomorodmelal.ir", "www.zomorodmelal.ir"})

PUBLIC_CATALOG = {
    72: {
        "title": "The Science and Practice of Chess Improvement",
        "category": "Digital book · Chess",
        "description": "An English 415-page chess study guide with an 84-day training plan, critical-position worksheets, game-review methods, and progress tracking.",
        "details": [
            "English PDF · 415 pages",
            "84-day structured training plan",
            "Critical-position worksheets and game review guidance",
            "Progress tracking for chess learners",
        ],
        "listed_price": "US $7.50",
        "expected_price_usd": "7.50",
    },
    225: {
        "title": "Taniya and the Little Baker Worms",
        "category": "Illustrated story · Children & families",
        "description": "An English illustrated 40-page landscape-format digital storybook for young readers, families and shared story time.",
        "details": [
            "English illustrated PDF · 40 landscape pages",
            "Colorful story for shared reading",
            "Suggested ages 3–8 with adult guidance",
        ],
        "listed_price": "US $4.00",
        "expected_price_usd": "4.00",
    },
    879: {
        "title": "Atelier Interior — Client-Ready Website Kit",
        "category": "Website kit · Interior design",
        "description": "A responsive studio website starter with project gallery, editable contact details, quote inquiry and WhatsApp handoff.",
        "details": [
            "Downloadable ZIP: HTML, CSS, JavaScript and setup instructions",
            "Portfolio pages, quote inquiry and WhatsApp handoff",
            "Five original SVG illustrations",
            "One-site/client license; demo photography is not included",
        ],
        "listed_price": "US $6.80",
        "expected_price_usd": "6.80",
    },
}


def _approved_purchase_url(request, product):
    """Link only to the *effective* private TRX gateway after all its gates pass.

    Public Saeit may not contain the private gateway modules at all.
    No optimistic purchase URL is rendered if components are missing or
    live rights, verified delivery, HTTPS, host or URL registration disagree.
    """
    try:
        from django.urls import reverse, resolve
        from services.mpw_trx_commercial_context import checkout_flags
        from services.mpw_trx_public_catalog import public_trx_product
        if checkout_flags(request).get("mpw_trx_easy_enabled") is not True:
            return None
        if public_trx_product(product.pk) is None:
            return None
        path = reverse("mpw_commerce:book", args=[product.pk])
        if resolve(path).url_name != "book":
            return None
        if not path.startswith("/commerce/book/"):
            return None
        return path
    except Exception:
        # Any missing private component, migration, provider or URL is a HOLD,
        # not an invitation to generate an invoice or mark a sale as live.
        return None


def brand_product_detail(request, product_id):
    """Never expose one company's product page as the other's sales offer."""
    host = request.get_host().split(":")[0].lower()
    if host in ZOMOROD_HOSTS:
        return zomorod_product_detail(request, product_id)
    if host not in MPW_HOSTS:
        raise Http404("Host not supported")
    if product_id not in PUBLIC_CATALOG:
        raise Http404("Catalog product not listed")
    item = PUBLIC_CATALOG[product_id]
    try:
        db_product = Product.objects.filter(pk=product_id, active=True).first()
    except DatabaseError:
        # Optional catalog migrations must not turn product discovery into 500.
        # This is a noindex preview, never a claim of sale readiness.
        logging.getLogger(__name__).warning(
            "MojPlayWin catalog lookup unavailable; page remains informational"
        )
        db_product = None
    # Matching the public product name is necessary; a reused database ID
    # must not be associated with someone else's digital product.
    # The card must also match the actual database currency and exact price.
    # Title-only matching can show a stale/false USD offer or count it as
    # verified when a changed listing now charges a different amount.
    matched = bool(
        db_product
        and db_product.title.strip() == item["title"]
        and db_product.currency == "USD"
        and db_product.price == Decimal(item["expected_price_usd"])
    )
    if matched:
        try:
            from .commerce_funnel import record_funnel_event
            record_funnel_event(request, "view_item", db_product)
        except Exception:
            # Analytics must not take down a validated product detail page.
            logging.getLogger(__name__).warning(
                "MojPlayWin product view telemetry unavailable"
            )
    # The live private gateway may already exist on cPanel even though its
    # source is excluded from this public repository. Respect its actual
    # merchant, rights, product-asset and route checks before exposing checkout.
    purchase_url = _approved_purchase_url(request, db_product) if matched else None
    available_for_checkout = bool(purchase_url)
    context = {
        "catalog": item,
        "product_id": product_id,
        "canonical": f"https://mojplaywin.com/store/product/{product_id}/",
        "listed_in_database": matched,
        "purchase_available": available_for_checkout,
        "approved_purchase_url": purchase_url,
        "database_price_usd": (
            str(db_product.price) if matched and db_product.currency == "USD"
            else None
        ),
        "return_path": "/store/",
        "is_preview": not matched,
    }
    response = render(request, "mojplaywin/product_detail.html", context)
    # A buy button depends on mutable merchant, rights and gateway gates.
    # Never cache a stale CTA after the checkout is revoked or put on hold.
    response["Cache-Control"] = "private, no-store, max-age=0, must-revalidate"
    response["Pragma"] = "no-cache"
    if not matched:
        response["X-Robots-Tag"] = "noindex, nofollow"
    return response
