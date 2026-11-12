"""Read-only, rights-filtered additions to MojPlayWin's curated storefront.

Only independently published products appear. A visible item never changes
payment availability, invents an order, or grants a download entitlement.
"""
from __future__ import annotations

import re
from decimal import Decimal

FEATURED_IDS = frozenset((72, 225, 879))
MAX_VISIBLE = 48


def _sha(value):
    return type(value) is str and re.fullmatch(r"[a-fA-F0-9]{64}", value) is not None


def _factory_path(value, kind):
    """Reject external redirects, encoded traversal and arbitrary file paths."""
    if type(value) is not str or len(value) > 250 or ".." in value:
        return False
    slug = r"[a-z0-9][a-z0-9-]{1,90}"
    filename = r"index\.html" if kind == "page" else r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}\.zip"
    return re.fullmatch(r"/factory-releases/" + slug + r"/" + filename, value) is not None


def catalog_card(product, paid_ids):
    """Classify one active published USD product without DB writes or imports."""
    if (product is None or product.active is not True or product.currency != "USD"
            or type(product.pk) is not int or product.pk <= 0
            or product.pk in FEATURED_IDS):
        return None
    meta = product.metadata
    if type(meta) is not dict:
        return None
    summary = meta.get("summary") or meta.get("seo_description") or ""
    summary = summary.strip()[:320] if type(summary) is str else ""

    if product.price == Decimal("0"):
        page = meta.get("factory_public_url")
        download = meta.get("factory_public_download_url")
        article = getattr(product, "knowledge_article", None)
        if (meta.get("factory_origin") != "saeit_vps"
                or meta.get("factory_storefront") != "mojplaywin"
                or meta.get("factory_status") != "published_free"
                or meta.get("factory_commercial_status") != "published_free_download_no_checkout"
                or meta.get("factory_publication_permission") is not True
                or meta.get("factory_software_qa") != "passed"
                or not _sha(meta.get("factory_bridge_sha256"))
                or not _factory_path(page, "page")
                or not _factory_path(download, "zip")
                or page.rsplit("/", 1)[0] != download.rsplit("/", 1)[0]
                or article is None or getattr(article, "published", False) is not True):
            return None
        return {
            "id": product.pk, "title": product.title, "description": summary,
            "url": page, "label": "View verified free release",
            "type": "Free published software", "price": "FREE",
        }

    catalog_sha = meta.get("sha256")
    rights_sha = meta.get("rights_asset_sha256")
    if (product.price <= 0 or product.pk not in paid_ids
            or meta.get("rights_cleared") is not True
            or meta.get("publication_approved") is not True
            or meta.get("sales_enabled") is not True
            or not _sha(catalog_sha) or not _sha(rights_sha)
            or not _sha(meta.get("rights_document_sha256"))
            or catalog_sha.lower() != rights_sha.lower()):
        return None
    return {
        "id": product.pk, "title": product.title, "description": summary,
        "url": "/store/product/{}/".format(product.pk),
        "label": "View verified product details",
        "type": "Approved digital product",
        "price": "{} USD".format(product.price),
    }


def verified_catalog_cards():
    """Bounded database-only discovery; no payment, filesystem or customer data."""
    from django.conf import settings
    from .models import Product

    ids = getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ())
    paid_ids = frozenset(
        value for value in ids
        if type(value) is int and value > 0
    ) if isinstance(ids, (tuple, list, set, frozenset)) else frozenset()
    products = (
        Product.objects.filter(active=True, currency="USD")
        .exclude(pk__in=FEATURED_IDS)
        .select_related("knowledge_article")
        .order_by("-id")[:250]
    )
    visible = []
    for product in products:
        card = catalog_card(product, paid_ids)
        if card is not None:
            visible.append(card)
        if len(visible) >= MAX_VISIBLE:
            break
    return visible
