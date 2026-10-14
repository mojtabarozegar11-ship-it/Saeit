"""Minimal reusable context policy for the *existing* MojPlayWin branded_store.

The deployed site routes /store/ through core.brand_views.branded_store, not
core.commerce_views.store_home. This adapter deliberately does not modify any
routes or attempt to publish inactive products.
"""
from .factory_storefront import presentation


def safe_brand_store_context(brand, products):
    if brand is None or getattr(brand, "code", None) != "mojplaywin":
        raise ValueError("MojPlayWin brand identity is required")
    factory_cards, nonfactory_products = presentation(products)
    return {
        "brand": brand,
        "products": nonfactory_products,
        "other_products": nonfactory_products,
        "factory_cards": factory_cards,
    }
