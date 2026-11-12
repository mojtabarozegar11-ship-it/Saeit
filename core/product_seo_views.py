"""Safe public SEO surfaces for active native catalog products."""
import json
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.urls import Resolver404, resolve
from django.utils.html import strip_tags
from .models import Product
from .mojplaywin_catalog import FEATURED_IDS, catalog_card

def public_product_url(product):
    return "/store/product/{}/".format(product.pk)

def public_product_description(product, brand="Zomorod Melal"):
    metadata = product.metadata if isinstance(product.metadata, dict) else {}
    description = metadata.get("seo_description") or metadata.get("description") or metadata.get("summary") or ""
    return strip_tags(str(description)).strip()[:500] or "{} — {} | {}".format(product.title, product.product_type, brand)

def storefront_for_host(host, currency):
    """Return the explicitly supported storefront, never infer from Host headers."""
    name = host.split(":", 1)[0].lower().rstrip(".")
    if name in ("zomorodmelal.ir", "www.zomorodmelal.ir"):
        return "zomorod"
    if (name in ("mojplaywin.com", "www.mojplaywin.com")
            and currency == "USD"):
        return "mojplaywin"
    return None


def approved_guest_checkout_route(product_id):
    """Link only to an existing route backed by the reviewed guest adapter.

    Resolving a URL never creates an invoice or touches the payment provider.
    An absent/unreviewed route is not represented as a working checkout.
    """
    if type(product_id) is not int or product_id <= 0:
        return None
    target = "/store/product/{}/checkout/".format(product_id)
    try:
        match = resolve(target)
    except Resolver404:
        return None
    view = match.func
    if (match.kwargs.get("product_id") != product_id
            or getattr(view, "__name__", None) != "product_checkout"
            or getattr(view, "__module__", None) != "services.mpw_trx_guest_commerce"):
        return None
    return target


def product_detail(request, product_id):
    host = request.get_host()
    # No product query or SEO exposure to unrecognized Host headers.
    if storefront_for_host(host, "USD") is None:
        raise Http404
    product = Product.objects.filter(pk=product_id, active=True).first()
    if product is None:
        raise Http404
    site = storefront_for_host(host, product.currency)
    if site is None:
        raise Http404

    metadata = product.metadata if isinstance(product.metadata, dict) else {}
    if site == "mojplaywin" and product.pk not in FEATURED_IDS:
        # Do not leak arbitrary active USD products from Zomorod's shared DB.
        # Additional paid/free items must first pass the SAME eligibility
        # policy used by the public MojPlayWin catalog.
        allowed = getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ())
        if not isinstance(allowed, (tuple, list, set, frozenset)):
            allowed = ()
        paid_ids = frozenset(
            value for value in allowed if type(value) is int and value > 0
        )
        if catalog_card(product, paid_ids) is None:
            raise Http404
    description = public_product_description(product, "MojPlayWin" if site == "mojplaywin" else "Zomorod Melal")
    image = metadata.get("seo_image") or metadata.get("image_url")
    image = image if isinstance(image, str) and image.startswith("https://") and len(image) < 1024 else None

    domain = "mojplaywin.com" if site == "mojplaywin" else "zomorodmelal.ir"
    url = "https://" + domain + public_product_url(product)
    schema = {"@context": "https://schema.org", "@type": "Product",
              "name": product.title, "description": description, "url": url}
    if image:
        schema["image"] = [image]

    # A product page is not itself evidence of a payable order or asset rights.
    # For MojPlayWin, price claims must be tied to the exact approved file and
    # its owner authorization; an inactive/mismatched product stays hidden.
    catalog_sha = metadata.get("sha256")
    rights_sha = metadata.get("rights_asset_sha256")
    rights_doc = metadata.get("rights_document_sha256")
    def valid_sha(value):
        return isinstance(value, str) and len(value) == 64 and all(
            ch in "0123456789abcdef" for ch in value.lower()
        )
    approved_paid = (
        site == "mojplaywin" and product.currency == "USD"
        and product.price > 0 and metadata.get("rights_cleared") is True
        and metadata.get("publication_approved") is True
        and valid_sha(catalog_sha) and valid_sha(rights_sha)
        and valid_sha(rights_doc)
        and catalog_sha.lower() == rights_sha.lower()
    )
    allowed_ids = getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ())
    if not isinstance(allowed_ids, (tuple, list, set, frozenset)):
        allowed_ids = ()
    allowed_ids = frozenset(x for x in allowed_ids if type(x) is int and x > 0)
    # The TRX storefront already requires explicit public SKU authorization,
    # current asset-bound publication rights, and a positive USD price.
    # Do not add an unrelated legacy Zomorod sales_enabled flag: the
    # owner-attested MojPlayWin rights release does not set that flag.
    can_list_offer = (
        product.currency in ("USD", "EUR", "IRR", "CAD")
        and product.price >= 0
        and (
            (site == "mojplaywin" and approved_paid and product.pk in allowed_ids)
            or (site != "mojplaywin" and metadata.get("sales_enabled") is True)
        )
    )
    checkout_url = (approved_guest_checkout_route(product.pk)
                    if site == "mojplaywin" and can_list_offer else None)
    if can_list_offer:
        schema["offers"] = {
            "@type": "Offer", "url": url, "price": str(product.price),
            "priceCurrency": product.currency,
            "availability": (
                "https://schema.org/InStock"
                if metadata.get("in_stock") is True
                else "https://schema.org/PreOrder"
            ),
        }
    return render(request, "core/product_detail.html", {
        "product": product, "description": description,
        "image": image, "schema_json": json.dumps(
            schema, ensure_ascii=False
        ).replace("<", "\\u003c"),
        "canonical": url, "mojplaywin_store": site == "mojplaywin",
        "can_list_offer": can_list_offer, "checkout_url": checkout_url,
    })
