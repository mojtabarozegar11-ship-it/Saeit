"""Resolve only the effective, guest-capable, privately gated TRX checkout.

The private app declares a legacy namespaced mpw_commerce:book URL and later
PREPENDS the actual customer route mpw_trx_public_product at the exact same
path. Reverse of the legacy name succeeds but resolve() reaches the public
route instead, so checking for the legacy route name falsely blocks sales.
A mere matching path is unsafe: require the exact effective callable object.
"""
from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)


def verified_guest_checkout_url(product_id):
    """Return the effective private checkout path or None without side effects."""
    if type(product_id) is not int or product_id <= 0:
        return None
    try:
        from django.urls import reverse, resolve
        # Imported only on the private cPanel runtime. Public source alone
        # cannot assert the customer checkout exists or is operational.
        from services.mpw_trx_public_pages import product_checkout

        expected_path = f"/commerce/book/{product_id}/"
        for route_name in ("mpw_trx_public_product", "mpw_trx_checkout"):
            try:
                path = reverse(route_name, kwargs={"product_id": product_id})
            except Exception:
                continue
            if path != expected_path:
                continue
            match = resolve(path)
            if match.namespaces or match.url_name != route_name:
                continue
            callback = match.func
            if route_name == "mpw_trx_public_product":
                if callback is product_checkout:
                    return path
            elif (
                getattr(callback, "__name__", "") == "product_checkout"
                and getattr(callback, "__module__", "")
                == "services.mpw_trx_guest_commerce"
            ):
                return path
        return None
    except Exception as exc:
        # Incorrect URL imports, absent private gateway and route shadows are
        # fail-closed. Never forge a checkout link from the product ID alone.
        LOGGER.warning("Effective MPW checkout route unavailable: %s",
                       type(exc).__name__)
        return None
