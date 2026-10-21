#!/usr/bin/env python3
"""Read-only, sanitized introspection of live delivery gate; no transaction or order writes."""
import ast
import copy
import inspect
import json
import os
from pathlib import Path
import sys
from decimal import Decimal

APP=Path("/home/zomorod2/Saeit-staging")
os.chdir(APP);sys.path.insert(0,str(APP))
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from core.models import Product
from core.cryptopay_checkout import product_delivery_ready
x=Product.objects.get(pk=879)
ref=Product.objects.filter(pk=225).first()
known={}
for p in (x,ref):
    if p is None:continue
    try:gate=bool(product_delivery_ready(p))
    except Exception as exc:gate="error:"+type(exc).__name__
    m=p.metadata if isinstance(p.metadata,dict) else {}
    known[str(p.pk)]={"delivery_ready":gate,"product_type":p.product_type,"active":p.active,
                      "metadata_keys":sorted(m),"fulfillment_status":str(m.get("fulfillment_status")),
                      "mpw_commerce_keys":sorted(m.get("mpw_commerce",{})) if isinstance(m.get("mpw_commerce"),dict) else []}
trial=copy.copy(x)
trial.active=True
trial.metadata=copy.deepcopy(x.metadata)
trial.metadata.update({
  "asset_verified":True,"license_verified":True,"quality_approved":True,
  "factory_publication_permission":True,"checkout_enabled":True,"payment_live":True,
  "sales_enabled":True,"in_stock":True,"private_asset_installed":True,
  "mpw_private_file_prepared":True,"fulfillment_status":"ready",
  "format":"ZIP","product_id":"atelier-interior-kit-v1",
})
trial.metadata["mpw_commerce"]["enabled"]=True
variants={}
for kind in ("full_flags","book_product_type","book_metadata_overlay"):
    p=copy.copy(trial)
    p.metadata=copy.deepcopy(trial.metadata)
    if kind=="book_product_type" and ref:p.product_type=ref.product_type
    if kind=="book_metadata_overlay" and ref:
        rm=ref.metadata
        p.metadata.update({k:v for k,v in rm.items() if k in ("fulfillment_status","mpw_private_file_prepared","private_asset_installed","format")})
    try:variants[kind]=bool(product_delivery_ready(p))
    except Exception as exc:variants[kind]="error:"+type(exc).__name__
try:
    source=inspect.getsource(product_delivery_ready)
    tree=ast.parse(source)
    string_literals=sorted({n.value for n in ast.walk(tree) if isinstance(n,ast.Constant)
        and isinstance(n.value,str) and 1<=len(n.value)<=55
        and "/" not in n.value and "\\" not in n.value and " " not in n.value
        and not any(s in n.value.lower() for s in ("token","secret","password","key","wallet"))})
except (OSError,TypeError):
    string_literals=[]
names=sorted(x for x in product_delivery_ready.__code__.co_names if not x.startswith("__"))
print("ATELIER_DELIVERY_GATE_SANITIZED="+json.dumps({
    "probes":known,"variants":variants,"function_external_names":names,
    "short_safe_literals":string_literals,
    "risk":"source_not_printed_no_payment_no_db_write",
},sort_keys=True))
