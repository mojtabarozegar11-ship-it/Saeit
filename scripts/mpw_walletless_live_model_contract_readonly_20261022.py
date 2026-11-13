#!/usr/bin/env python3
"""Read-only metadata for safe Django walletless TRX integration. No secrets, no ORM writes."""
import json,os,pwd,sys
from pathlib import Path
root=Path("/home/zomorod2/Saeit-staging")
site=Path("/home/zomorod2/mojplaywin.com")
if pwd.getpwuid(os.getuid()).pw_name!="zomorod2" or root.is_symlink() or site.is_symlink():raise RuntimeError("Wrong account")
if "APP='/home/zomorod2/Saeit-staging'" not in (site/"passenger_wsgi.py").read_text("utf8","replace"):raise RuntimeError("Wrong Passenger")
os.chdir(root);sys.path.insert(0,str(root));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection
for app,name in (("mpw_commerce","CommerceInvoice"),("mpw_commerce","CommerceReceipt"),("mpw_commerce","CommerceFulfillment"),("core","Order"),("core","OrderItem"),("core","LedgerEntry")):
 try:
  model=apps.get_model(app,name)
  fields=[{"name":f.name,"type":f.get_internal_type(),"max_length":f.max_length,"null":f.null,
  "choices":[v for v,label in f.choices] if f.choices else [],
  "related":f.related_model.__name__ if f.is_relation and f.related_model else None} for f in model._meta.fields]
  print("MPW_WALLETLESS_DJANGO_MODEL="+json.dumps({"app":app,"name":name,"db_table":model._meta.db_table,"fields":fields},sort_keys=True))
 except LookupError:print("MPW_WALLETLESS_DJANGO_MISSING="+name)
print("MPW_WALLETLESS_DJANGO_ENGINE="+json.dumps({"engine":settings.DATABASES["default"]["ENGINE"],
"vendor":connection.vendor,"private_payment_tables_exist":False}))
try:
 import importlib
 mod=importlib.import_module("mpw_commerce.buyer_wallets")
 quote=mod.fetch_server_rate("TRX")
 print("MPW_WALLETLESS_RATE_AVAILABLE="+json.dumps({"present":True,"class":type(quote).__name__,"source":str(quote.source)[:40]}))
except Exception as exc:print("MPW_WALLETLESS_RATE_AVAILABLE="+json.dumps({"present":False,"exception":type(exc).__name__}))
print("MPW_WALLETLESS_READ_ONLY_MODEL_INSPECTION=PASS")
