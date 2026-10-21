#!/usr/bin/env python3
"""No-write final launch simulation for product 879; no fake payment or ledger entry."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path("/home/zomorod2")
APP=ROOT/"Saeit-staging"
PATH=ROOT/".private_mojplaywin_digital_products/atelier-interior-kit-v1-original-vector-edition.zip"
SHA="20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
def main():
    if PATH.is_symlink() or not PATH.is_file() or hashlib.sha256(PATH.read_bytes()).hexdigest()!=SHA:
        raise SystemExit("NO_ORIGINAL_PRIVATE_BUNDLE")
    with zipfile.ZipFile(PATH) as z:
        names=z.namelist()
        if len(names)!=11 or z.testzip() is not None:
            raise SystemExit("ZIP_INTEGRITY_FAILURE")
        images=[x for x in names if x.endswith(".svg")]
        if len(images)!=5:
            raise SystemExit("NOT_ALL_FIVE_ORIGINAL_IMAGES")
        for x in images:
            t=ET.fromstring(z.read(x))
            if not t.tag.endswith("svg"):raise SystemExit("SVG_INVALID")
            if any("http" in k.lower() for a in t.iter() for k in a.attrib if k not in ("xmlns",)):
                raise SystemExit("EXTERNAL_SVG_RESOURCE")
        html=z.read("index.html")
        js=z.read("app.js")
        cfg=z.read("config.js")
        readme=z.read("README.md")
        if b".jpg" in html+js+cfg+z.read("styles.css"):
            raise SystemExit("MISSED_THIRD_PARTY_PHOTO_LINK")
        if not all(x in names for x in ("index.html","styles.css","app.js","config.js","README.md")):
            raise SystemExit("MISSING_WEB_SOURCE")
        if b"ATELIER_CONFIG" not in cfg or b"WhatsApp" not in readme:
            raise SystemExit("NOT_EDITABLE_OR_NO_CONTACT_DOC")
        if not all(term in readme.lower() for term in (b"non-exclusive",b"photographs visible",b"not included")):
            raise SystemExit("MISSING_PURCHASER_DISCLOSURE")
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django
    django.setup()
    from core.models import Product
    from core.cryptopay_checkout import product_delivery_ready
    from django.urls import resolve,reverse
    p=Product.objects.get(pk=879)
    m=p.metadata
    if p.active or str(p.price) not in ("6.8","6.80") or m.get("sha256")!=SHA:
        raise SystemExit("SCOPE_INACTIVE_ROW_CHANGED")
    candidate=copy.copy(p)
    mm=copy.deepcopy(m)
    mm.update({"quality_approved":True,"factory_publication_permission":True,"checkout_enabled":True,
               "payment_live":True,"sales_enabled":True,"in_stock":True})
    mm["mpw_commerce"]["enabled"]=True
    candidate.metadata=mm
    candidate.active=True
    simulated=bool(product_delivery_ready(candidate))
    paths={
      "product":resolve("/store/product/879/").func.__module__,
      "checkout":resolve("/store/product/879/checkout/").func.__module__,
      "download":resolve(reverse("mpw_commerce:download",kwargs={"item_id":879})).func.__module__,
    }
    out={"sku":"atelier-interior-kit-v1","product_id":879,"mode":"read_only_in_memory_flags",
         "archive_sha_verified":True,"bundled_original_svg_images":5,
         "file_format":"ZIP","license_included":True,
         "intended_price_usd":"6.80","route_owners":paths,
         "candidate_product_delivery_ready":simulated,"public_active_now":False,
         "real_payment_tested":False,"real_buyer_download_tested":False}
    print("ATELIER_VECTOR_SALE_CANDIDATE_PROBE="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
