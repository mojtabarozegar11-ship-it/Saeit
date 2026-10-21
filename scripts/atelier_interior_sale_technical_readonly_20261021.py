#!/usr/bin/env python3
"""No-write inspection of exact Atelier SKU 879 checkout/delivery and image license evidence."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile
from urllib.parse import urlparse

APP=Path("/home/zomorod2/Saeit-staging")
STOCK=Path("/home/zomorod2/.private_mojplaywin_digital_products/atelier-interior-kit-v1-repacked.zip")
EXPECTED="98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"
SKU="atelier-interior-kit-v1"
TITLE="Atelier Interior — Client-Ready Website Kit"
def run():
    if APP.is_symlink() or STOCK.is_symlink() or not STOCK.is_file() or STOCK.parent.is_symlink():
        raise SystemExit("UNSAFE_PRIVATE_SOURCE")
    if hashlib.sha256(STOCK.read_bytes()).hexdigest()!=EXPECTED:
        raise SystemExit("PRIVATE_ZIP_NOT_EXACT")
    with zipfile.ZipFile(STOCK) as z:
        members=z.namelist()
        docs=[n for n in members if n.lower() in ("license","license.md","license.txt","readme.md")]
        readme=z.read("README.md").decode("utf-8","replace")
        rights=re.findall(r"(?im)^.{0,30}(?:license|copyright|image rights|commercial use|resell|redistribut).{0,140}$",readme)
        texts="\n".join(z.read(n).decode("utf-8","replace") for n in members if n.endswith((".html",".css",".js",".md")))
        domains=sorted({urlparse(s).hostname for s in re.findall(r"https?://[^\s\"'<>\\)]+",texts) if urlparse(s).hostname})
        photos=[x for x in members if x.endswith((".jpg",".png",".webp"))]
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    import django
    django.setup()
    from core.models import Product
    from django.urls import reverse,resolve
    p=Product.objects.filter(pk=879,title=TITLE).first()
    if not p or p.metadata.get("sku")!=SKU:
        raise SystemExit("EXACT_INACTIVE_RECORD_NOT_FOUND")
    from core.cryptopay_checkout import product_delivery_ready
    from mpw_commerce.entitlements import can_access_purchased_digital_item
    routes={}
    for name,path in (("product","/store/product/879/"),("checkout","/store/product/879/checkout/"),("download",reverse("mpw_commerce:download",kwargs={"item_id":879}))):
        try:
            m=resolve(path)
            routes[name]={"route":path,"resolves":True,"handler":m.func.__module__}
        except Exception as e:routes[name]={"route":path,"resolves":False,"error_type":type(e).__name__}
    m=p.metadata
    report={
        "sku":SKU,"id":p.pk,"read_only":True,
        "native_inactive":not p.active,"price_usd_6_80":p.currency=="USD" and str(p.price) in ("6.8","6.80"),
        "private_zip_exact":True,"photo_assets_count":len(photos),
        "archive_has_license_or_readme":bool(docs),
        "readme_has_license_wording":bool(rights),
        "image_provenance_independent":False,
        "external_resource_domains":domains,
        "checkout_route_resolves":routes["checkout"]["resolves"],
        "download_route_resolves":routes["download"]["resolves"],
        "checkout_route_owner":routes["checkout"].get("handler"),
        "download_route_owner":routes["download"].get("handler"),
        "native_delivery_ready":bool(product_delivery_ready(p)),
        "anonymous_purchase_entitled":bool(can_access_purchased_digital_item(879,-991829)),
        "license_verified":m.get("license_verified") is True,
        "quality_approved":m.get("quality_approved") is True,
        "public_sale_enabled":bool(p.active and m.get("mpw_commerce",{}).get("enabled")),
        "real_payment_and_download_tested":False,
    }
    if not report["native_inactive"] or report["public_sale_enabled"] or report["anonymous_purchase_entitled"]:
        raise SystemExit("FAIL_CLOSED_UNEXPECTED_PUBLIC_SALE_OR_ACCESS")
    print("ATELIER_SALE_TECHNICAL_PROBE="+json.dumps(report,sort_keys=True))
if __name__=="__main__":
    run()
