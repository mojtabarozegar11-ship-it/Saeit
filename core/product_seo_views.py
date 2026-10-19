"""Safe public SEO surfaces for active native catalog products."""
import json
from django.http import Http404
from django.shortcuts import render
from django.utils.html import strip_tags
from .models import Product

def public_product_url(product):
    return "/store/product/{}/".format(product.pk)

def public_product_description(product):
    metadata = product.metadata if isinstance(product.metadata, dict) else {}
    description = metadata.get("seo_description") or metadata.get("description") or metadata.get("summary") or ""
    return strip_tags(str(description)).strip()[:500] or "{} — {} | Zomorod Melal".format(product.title,product.product_type)

def product_detail(request, product_id):
    if request.get_host().split(":")[0].lower() not in ("zomorodmelal.ir","www.zomorodmelal.ir"):
        raise Http404
    product = Product.objects.filter(pk=product_id,active=True).first()
    if product is None:
        raise Http404
    metadata=product.metadata if isinstance(product.metadata,dict) else {}
    description=public_product_description(product)
    image=metadata.get("seo_image") or metadata.get("image_url")
    image=image if isinstance(image,str) and image.startswith("https://") and len(image)<1024 else None
    url="https://zomorodmelal.ir"+public_product_url(product)
    schema={"@context":"https://schema.org","@type":"Product","name":product.title,"description":description,"url":url}
    if image: schema["image"]=[image]
    # An Offer is supplied only for explicitly sale-ready products, never previews.
    if metadata.get("sales_enabled") is True and product.currency in ("USD","EUR","IRR","CAD") and product.price >= 0:
        schema["offers"]={"@type":"Offer","url":url,"price":str(product.price),"priceCurrency":product.currency,
        "availability":"https://schema.org/InStock" if metadata.get("in_stock") is True else "https://schema.org/PreOrder"}
    return render(request,"core/product_detail.html",{"product":product,"description":description,
        "image":image,"schema_json":json.dumps(schema,ensure_ascii=False).replace("<","\\u003c"),
        "canonical":url})
