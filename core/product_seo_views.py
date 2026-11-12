"""Safe public SEO surfaces for active native catalog products."""
import json
from django.http import Http404
from django.shortcuts import render
from django.utils.html import strip_tags
from .models import Product

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
    can_list_offer = (
        metadata.get("sales_enabled") is True
        and product.currency in ("USD", "EUR", "IRR", "CAD")
        and product.price >= 0
        and (site != "mojplaywin" or approved_paid)
    )
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
        "can_list_offer": can_list_offer,
    })
