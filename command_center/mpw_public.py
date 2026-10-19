"""Additive public view data; strict domain and feature flag prevent affecting sibling sites."""
import re
from django.conf import settings
from .models import MpwRecord, TENANT, local_path

HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
SAFE_IMAGE = re.compile(r"^site/[a-zA-Z0-9_./-]+\.(?:webp|png|jpg|jpeg)$")


def is_main(request):
    return request.get_host().split(":")[0].lower() in HOSTS


def safe_payload(kind, payload):
    if not isinstance(payload, dict):
        return None
    if kind == "content":
        url = payload.get("url", "")
        image = payload.get("image", "")
        if not local_path(url, allow_empty=True):
            return None
        if image and (not SAFE_IMAGE.fullmatch(image) or ".." in image.split("/")):
            return None
        return {"slot": payload.get("slot") if payload.get("slot") in ("section", "row", "card") else "card",
                "group": str(payload.get("group") or "editorial")[:80],
                "title": str(payload.get("title") or "")[:200],
                "body": str(payload.get("body") or "")[:2000],
                "url": url, "image": image}
    if kind == "offer":
        path = payload.get("checkout_path", "")
        if not local_path(path, allow_empty=True):
            return None
        try:
            from decimal import Decimal
            price = Decimal(str(payload.get("price", "")))
            if price < 0 or price > 999999999 or not price.is_finite():
                return None
        except (ValueError, TypeError, ArithmeticError):
            return None
        currency = str(payload.get("currency") or "USD").upper()
        if currency not in ("USD", "EUR", "IRR", "CAD"):
            return None
        approved = bool(payload.get("rights_verified"))
        if not approved:
            return None
        payable = (bool(getattr(settings, "MPW_ENABLE_CHECKOUT", False))
                   and bool(payload.get("payment_verified"))
                   and bool(payload.get("delivery_verified"))
                   and bool(payload.get("payment_evidence"))
                   and bool(payload.get("delivery_evidence"))
                   and bool(path))
        return {"title": str(payload.get("title") or "")[:200],
                "body": str(payload.get("body") or "")[:2000],
                "price": price, "currency": currency,
                "checkout_path": path if payable else "", "payable": payable}
    return None


def public_context(request):
    if not is_main(request) or not getattr(settings, "MPW_CONTROL_ENABLED", False):
        return {"mpw_managed_blocks": [], "mpw_managed_offers": []}
    path = request.path
    blocks, offers = [], []
    for row in MpwRecord.objects.filter(tenant=TENANT, kind="content",
                                        page_path=path).exclude(published_snapshot={}).order_by("key")[:100]:
        item = safe_payload("content", row.published_snapshot)
        if item:
            blocks.append({**item, "key": row.key})
    if path == "/store/":
        for row in MpwRecord.objects.filter(tenant=TENANT, kind="offer",
                                            page_path="/store/").exclude(published_snapshot={}).order_by("key")[:100]:
            item = safe_payload("offer", row.published_snapshot)
            if item:
                offers.append({**item, "key": row.key})
    return {"mpw_managed_blocks": blocks, "mpw_managed_offers": offers}
