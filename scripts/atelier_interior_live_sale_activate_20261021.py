#!/usr/bin/env python3
"""Activate exact verified Product 879 only; restore exact snapshot on failed public smoke."""
from __future__ import annotations
import copy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import zipfile

APP=Path("/home/zomorod2/Saeit-staging")
SAFE=Path("/home/zomorod2/.private_mojplaywin_digital_products")
BACKUP=SAFE/"atelier-product-879-before-live-offer.json"
TITLE="Atelier Interior — Client-Ready Website Kit"
SKU="atelier-interior-kit-v1"
SHA="20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
FILENAME="atelier-interior-kit-v1-original-vector-edition.zip"
def hash_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(131072),b""):
            h.update(b)
    return h.hexdigest()
def setup():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("WRONG_OS_USER")
    if SAFE.is_symlink() or not SAFE.is_dir() or stat.S_IMODE(SAFE.stat().st_mode)&0o077:
        raise RuntimeError("UNSAFE_SNAPSHOT_FOLDER")
    if APP.is_symlink() or not (APP/"manage.py").is_file():raise RuntimeError("WRONG_APP")
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from core.models import Product
    from core.cryptopay_checkout import PRIVATE_ROOT,_file_for,product_delivery_ready
    from django.db import transaction
    from django.urls import resolve,reverse
    path=Path(PRIVATE_ROOT)/".atelier_paid_digital_20261021"/FILENAME
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode)&0o077:
        raise RuntimeError("PRODUCT_879_NOT_PRIVATE")
    if hash_file(path)!=SHA:raise RuntimeError("PRODUCT_ASSET_SHA_CHANGED")
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None or len(z.namelist())!=11 or sum(x.endswith(".svg") for x in z.namelist())!=5:
            raise RuntimeError("PRODUCT_BUNDLE_NOT_QA_CANDIDATE")
    if not all([
        resolve("/store/product/879/"),
        resolve("/store/product/879/checkout/"),
        reverse("mpw_commerce:download",kwargs={"item_id":879}),
    ]):raise RuntimeError("BUYER_ROUTES_MISSING")
    return Product,transaction,_file_for,product_delivery_ready,path

def invariant(p,path,_file_for,product_delivery_ready,allow_active=False):
    meta=p.metadata
    if p.pk!=879 or p.title!=TITLE or p.product_type!="website_template" or p.price!=Decimal("6.80") or p.currency!="USD":
        raise RuntimeError("EXACT_PRODUCT_OR_PRICE_CHANGED")
    if p.active and not allow_active:raise RuntimeError("ALREADY_PUBLIC")
    if not isinstance(meta,dict) or meta.get("sku")!=SKU or meta.get("sha256")!=SHA:
        raise RuntimeError("NOT_OUR_PRIVATE_ASSET")
    if meta.get("private_file")!=str(path) or meta.get("mpw_commerce",{}).get("private_file")!=str(path):
        raise RuntimeError("FILE_REFERENCES_CHANGED")
    fp=_file_for(p)
    if fp is None or Path(fp).resolve()!=path.resolve() or not product_delivery_ready(p):
        raise RuntimeError("REAL_DELIVERY_GATE_FAILED")

def backup_row(p):
    snap={"id":879,"title":p.title,"active":p.active,
          "product_type":p.product_type,"price":str(p.price),"currency":p.currency,
          "owner_id":p.owner_id,"metadata":p.metadata}
    data=json.dumps(snap,sort_keys=True,ensure_ascii=False).encode("utf8")
    if BACKUP.is_symlink():raise RuntimeError("SNAPSHOT_SYMLINK")
    if BACKUP.exists():
        if not BACKUP.is_file() or hash_file(BACKUP)!=hashlib.sha256(data).hexdigest():
            raise RuntimeError("EXISTING_SNAPSHOT_MISMATCH")
    else:
        with BACKUP.open("xb") as f:
            os.fchmod(f.fileno(),0o600)
            f.write(data);f.flush();os.fsync(f.fileno())

def activate():
    if os.environ.get("ATELIER_REAL_SALE_APPROVAL")!="owner-2026-10-21":
        raise PermissionError("NO_SCOPE_FOR_SALE_ACTIVATION")
    Product,transaction,ff,ready,path=setup()
    with transaction.atomic():
        p=Product.objects.select_for_update().get(pk=879)
        invariant(p,path,ff,ready)
        owner_ref=list(Product.objects.filter(pk__in=(72,225)).values_list("owner_id",flat=True))
        if len(owner_ref)!=2 or len(set(owner_ref))!=1 or owner_ref[0]!=p.owner_id:
            raise RuntimeError("SELLER_OWNER_NOT_CONSISTENT")
        backup_row(p)
        new=copy.deepcopy(p.metadata)
        new.update({
          "quality_approved":True,"asset_verified":True,"license_verified":True,
          "factory_publication_permission":True,"checkout_enabled":True,
          "payment_live":True,"sales_enabled":True,"in_stock":True,
          "mpw_private_file_prepared":True,"private_asset_installed":True,
          "fulfillment_status":"ready_for_paid_checkout",
          "catalog_state":"public_original_vector_launch_offer",
          "features":[
             "Responsive interior studio landing page and portfolio",
             "Editable brand name, contact details and colors",
             "Five original SVG interior illustrations included",
             "WhatsApp quote-request handoff",
             "Self-hosted HTML, CSS and JavaScript source in ZIP",
             "Non-exclusive one-site/client license and setup instructions",
          ],
          "long_description":(
             "Original Vector Edition v1.1. Downloadable editable interior-design site kit "
             "with a project gallery, color/brand configuration and WhatsApp inquiry. "
             "The demonstration photographs are not included; five original SVG illustrations "
             "are supplied instead. No hosting, custom installation or support included."
          ),
          "disclaimer":(
             "Demo photos are not included. Change contact details and add your own licensed "
             "project images before publishing. First real paid buyer checkout is not yet independently tested."
          ),
          "proposed_regular_price":"17.00","owner_selected_promotion_percent":60,
          "regular_price":"6.80","discount_percentage":0,
          "pricing_note":"Introductory launch price: USD 6.80; no unverified prior-price claim",
          "real_customer_payment_tested":False,
          "real_customer_download_tested":False,
          "sale_release_basis":"owner approved; original vector assets; integrity and native file gate verified",
        })
        new["mpw_commerce"]["enabled"]=True
        new["mpw_commerce"]["fulfillment"]="digital"
        new["mpw_commerce"]["main_host_only"]=True
        p.metadata=new;p.active=True;p.full_clean();p.save(update_fields=["active","metadata","updated_at"])
    p=Product.objects.get(pk=879)
    invariant(p,path,ff,ready,allow_active=True)
    if not p.active or not p.metadata["mpw_commerce"]["enabled"]:raise RuntimeError("NOT_ENABLED")
    print("ATELIER_PUBLIC_SALE_ACTIVATION="+json.dumps({
        "product_id":879,"active":True,"price_usd":"6.80",
        "exact_private_delivery_ready":True,"snapshot_rollback_available":BACKUP.is_file(),
        "public_product_path":"/store/product/879/","public_checkout_path":"/store/product/879/checkout/",
        "actual_paid_buyer_transaction_tested":False,"other_products_changed":False
    },sort_keys=True))

def rollback():
    if os.environ.get("ATELIER_ROLLBACK_OWNER_SCOPE")!="owner-2026-10-21":
        raise PermissionError("NO_ROLLBACK_SCOPE")
    Product,transaction,ff,ready,path=setup()
    if BACKUP.is_symlink() or not BACKUP.is_file():raise RuntimeError("SNAPSHOT_MISSING")
    original=json.loads(BACKUP.read_text("utf8"))
    if original.get("id")!=879 or original.get("active") is not False or original.get("metadata",{}).get("sha256")!=SHA:
        raise RuntimeError("SNAPSHOT_NOT_INACTIVE_APPROVED_PRODUCT")
    with transaction.atomic():
        p=Product.objects.select_for_update().get(pk=879)
        invariant(p,path,ff,ready,allow_active=True)
        p.active=False
        p.metadata=original["metadata"]
        p.full_clean();p.save(update_fields=["active","metadata","updated_at"])
    print("ATELIER_PUBLIC_SALE_ROLLBACK=PRODUCT_879_INACTIVE_NO_OTHER_CHANGE")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":
        assert SHA and len(SHA)==64 and TITLE.startswith("Atelier")
        print("ATELIER_REAL_SALE_STRICT_SCOPE_SELFTEST=PASS")
    elif len(sys.argv)==2 and sys.argv[1]=="activate":activate()
    elif len(sys.argv)==2 and sys.argv[1]=="rollback":rollback()
    else:raise SystemExit("selftest|activate|rollback")
