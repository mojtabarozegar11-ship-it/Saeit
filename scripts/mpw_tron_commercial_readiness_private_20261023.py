#!/usr/bin/env python3
"""Production context, model and catalog inspection. Strictly SELECT-only.

Print no addresses, transaction IDs, filenames, customer data, credentials,
product titles, wallet signatures, prices, DB names or source code.
"""
from __future__ import annotations
import inspect
import json
import os
import sys
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
ROOT=Path("/home/zomorod2/mojplaywin.com")
if not APP.is_dir() or APP.is_symlink() or ROOT.is_symlink():
    raise SystemExit("Unexpected cPanel paths")
if "APP='/home/zomorod2/Saeit-staging'" not in (ROOT/"passenger_wsgi.py").read_text("utf8","replace"):
    raise SystemExit("Unexpected Passenger application")
os.chdir(APP)
sys.path.insert(0,str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.urls import resolve
from django.apps import apps
from core.models import Product,PaymentIntent,OrderItem
from types import SimpleNamespace
try:
    from mpw_commerce.fulfillment import _private_file
except ImportError:
    _private_file=None
try:
    from mpw_commerce.buyer_orders import _eligible
except ImportError:
    _eligible=None

data={"scope":"read-only-production-commerce-readiness","financial_writes":0,"public_checkout_changed":False,
      "db_backend":connection.vendor, "catalog":{}, "handler":{}, "models":{}, "configuration":{}}
for product_id in (72,73):
    prod=Product.objects.filter(pk=product_id).first()
    if prod is None:
        data["catalog"][str(product_id)]={"exists":False}
        continue
    entry={"exists":True,"active":bool(prod.active),"currency_usd":str(prod.currency)=="USD",
           "product_type":str(prod.product_type)[:50],"positive_price":bool(prod.price>0)}
    try:
        entry["eligible"]=bool(_eligible(prod)) if _eligible else None
        item=SimpleNamespace(product=prod)
        path=_private_file(item) if _private_file else None
        entry["private_file_exists"]=bool(path and path.is_file() and not path.is_symlink())
    except Exception as exc:
        entry["private_file_exists"]=False
        entry["file_check_error_type"]=type(exc).__name__
    data["catalog"][str(product_id)]=entry
for url in ("/store/product/72/checkout/","/commerce/trx-easy/invoice/1/",
            "/commerce/trx-easy/start/72/","/store/product/72/"):
    try:
        match=resolve(url)
        callback=match.func
        data["handler"][url]={"mounted":True,"module":str(getattr(callback,"__module__",""))[:120],
                              "function":str(getattr(callback,"__name__",""))[:120]}
    except Exception as exc:
        data["handler"][url]={"mounted":False,"error_type":type(exc).__name__}
for mod in ("mpw_commerce","mpw_commerce.buyer_wallets","mpw_commerce.buyer_orders",
            "mpw_commerce.invoicing","mpw_commerce.settlement","mpw_commerce.fulfillment",
            "mpw_native_checkout"):
    try:
        o=__import__(mod,fromlist=["*"])
        data["models"][mod]={"importable":True,"path_under_app":bool(
            str(Path(getattr(o,"__file__", "/")).resolve()).startswith(str(APP)+"/"))}
    except Exception as exc:
        data["models"][mod]={"importable":False,"error_type":type(exc).__name__}
for flag in ("MPW_COMMERCE_RELEASE_READY","MPW_COMMERCE_REAL_RPC_ENABLED",
             "MPW_COMMERCE_AUTORECONCILE_ENABLED","MPW_COMMERCE_INVOICING_ENABLED",
             "MPW_COMMERCE_SETTLEMENT_ENABLED","MPW_COMMERCE_DOWNLOADS_ENABLED",
             "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED","MPW_WALLETLESS_TRX_PUBLIC_ENABLED"):
    data["configuration"][flag]=bool(getattr(settings,flag,False))
try:
    from mpw_commerce.invoicing import RECEIVERS
    v=RECEIVERS.get("TRX") if isinstance(RECEIVERS,dict) else None
    data["configuration"]["merchant_trx_receiver_configured"]=bool(
        isinstance(v,(tuple,list)) and len(v)==2 and v[0]=="tron-mainnet"
        and isinstance(v[1],str) and len(v[1])==34 and v[1].startswith("T"))
except Exception as exc:
    data["configuration"]["receiver_check_error_type"]=type(exc).__name__
try:
    from mpw_commerce.buyer_wallets import fetch_server_rate
    rate=fetch_server_rate("TRX")
    data["configuration"]["trx_quote_usable"]=bool(rate.usd_per_asset>0 and rate.observed_at)
except Exception as exc:
    data["configuration"]["trx_quote_usable"]=False
    data["configuration"]["trx_quote_error_type"]=type(exc).__name__
data["models"]["existing_payment_intent_rows"]=PaymentIntent.objects.exists()
data["models"]["existing_orderitem_rows"]=OrderItem.objects.exists()
print("MPW_COMMERCIAL_READINESS="+json.dumps(data,sort_keys=True))
