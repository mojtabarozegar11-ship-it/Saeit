"""Safety gate for commercial factory catalog presentation.

No 'was' or struck-through pricing: assessed values are not historical prices.
No paid checkout link unless both payment verification and delivery are proven.
This module never writes to database or activates a product.
"""
from decimal import Decimal, InvalidOperation

FREE_RECIPE="farm_enterprise_economics"
FREE_DOWNLOAD="/factory-releases/farm-enterprise-economics-v1/"
VALID_FACTORY_RECIPES={FREE_RECIPE,"water_budget_economics"}


def factory_card(product):
    metadata=product.metadata if isinstance(product.metadata,dict) else {}
    if not product.active or metadata.get("factory_origin")!="saeit_vps":
        return None
    if (metadata.get("factory_recipe") not in VALID_FACTORY_RECIPES or
        metadata.get("factory_publication_permission") is not True or
        metadata.get("factory_software_qa")!="passed"):
        return None
    try:
        price=Decimal(str(product.price))
    except (InvalidOperation,TypeError,ValueError):
        return None
    if not price.is_finite() or price<0 or product.currency!="USD":
        return None
    if price==Decimal("0"):
        if (metadata.get("factory_recipe")!=FREE_RECIPE or
            metadata.get("factory_commercial_status")!="published_free_download_no_checkout" or
            metadata.get("factory_public_download_url")!="/factory-releases/farm-enterprise-economics-v1/Farm_Enterprise_Economics_Toolkit_Free_v1.zip"):
            return None
        return {"name":product.title,"price":"Free","url":FREE_DOWNLOAD,
                "button":"Free download","kind":"free","discount_claim":None}
    if not all(metadata.get(flag) is True for flag in (
        "factory_paid_checkout_ready","factory_payment_mainnet_verified",
        "factory_fulfillment_production_verified")):
        return None
    if (metadata.get("factory_license_review")!="verified" or
        metadata.get("factory_support_review")!="verified"):
        return None
    path=metadata.get("factory_verified_checkout_url")
    if not isinstance(path,str) or not path.startswith("/checkout/") or any(
        c in path for c in ("\\","?", "#", "//", "\n", "\r")
    ):
        return None
    # No fake former prices. A 90% launch price is never a 90% historical discount.
    intro=metadata.get("factory_launch_reduction_percent")=="90"
    try:
        assessed=Decimal(metadata.get("factory_assessed_reference_usd","-1"))
    except (InvalidOperation,TypeError,ValueError):
        return None
    if intro and (not assessed.is_finite() or (assessed*Decimal("0.10")).quantize(Decimal("0.01"))!=price):
        return None
    return {"name":product.title,"price":f"USD ${price:.2f}",
            "url":path,"button":"Proceed to secure checkout","kind":"paid",
            "discount_claim":"90% below assessed launch valuation (not a former sale price)" if intro else None}


def presentation(products):
    factory=[]
    regular=[]
    for p in products:
        if isinstance(p.metadata,dict) and p.metadata.get("factory_origin")=="saeit_vps":
            card=factory_card(p)
            if card:
                factory.append(card)
        else:
            regular.append(p)
    return factory,regular
