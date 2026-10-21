#!/usr/bin/env python3
"""Read-only pre-money expert gate for the live MojPlayWin crypto checkout.

Never create or mutate production invoices/orders/receipts, don't send funds,
don't print wallet addresses, keys, private files, buyers, or transaction hashes.
Reports actual readiness defects; code presence is NOT payment verification.
"""
import collections
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
SITE=Path("/home/zomorod2/mojplaywin.com")
PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
WSGI=SITE/"passenger_wsgi.py"
if not APP.is_dir() or APP.is_symlink() or SITE.is_symlink() or not WSGI.is_file():
    raise SystemExit("FAIL_UNVERIFIED_MAIN_SITE")
if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
    raise SystemExit("FAIL_SITE_ROOT_MISMATCH")

os.chdir(APP)
sys.path.insert(0,str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.apps import apps
from django.urls import reverse, resolve
from django.test import RequestFactory
from django.utils import timezone
from types import SimpleNamespace
from core.models import Product
from mpw_commerce.product_checkout_page import product_checkout_page

def emit(key,data):
    print(key+"="+json.dumps(data,sort_keys=True,ensure_ascii=False,default=str))

warnings=[]
blocks=[]
flags={}
for name in ("MPW_COMMERCE_RELEASE_READY","MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
             "MPW_COMMERCE_INVOICING_ENABLED","MPW_COMMERCE_SETTLEMENT_ENABLED",
             "MPW_COMMERCE_REAL_RPC_ENABLED","MPW_COMMERCE_AUTORECONCILE_ENABLED",
             "MPW_COMMERCE_DOWNLOADS_ENABLED"):
    flags[name]=getattr(settings,name,False) is True
    if not flags[name]:blocks.append("runtime_flag_off:"+name)
emit("MPW_PREBUY_CRYPTO_FLAGS",flags)

models={}
for app,name in [("mpw_commerce","CommerceInvoice"),
                 ("mpw_commerce","CommerceReceipt"),
                 ("mpw_commerce","CommerceFulfillment"),
                 ("core","Order"),("core","LedgerEntry")]:
    try:
        m=apps.get_model(app,name)
        models[name]={"exists":True,"count":m.objects.count()}
    except Exception as e:
        models[name]={"exists":False,"error":type(e).__name__}
emit("MPW_PREBUY_CRYPTO_MODELS",models)

models_required=["CommerceInvoice","CommerceReceipt","CommerceFulfillment","Order","LedgerEntry"]
for name in models_required:
    if not models[name].get("exists"):blocks.append("model_unavailable:"+name)

for route in ("/commerce/checkout/order/","/commerce/checkout/challenge/",
              "/commerce/checkout/verify/","/commerce/checkout/invoice/",
              "/commerce/checkout/status/123456789/","/commerce/download/123456789/"):
    try:
        match=resolve(route)
        emit("MPW_PREBUY_ROUTE",{"path":route,"resolved":True,
             "module":match.func.__module__})
    except Exception as e:
        blocks.append("route_unavailable:"+route)
        emit("MPW_PREBUY_ROUTE",{"path":route,"resolved":False,"error":type(e).__name__})

readiness=[]
for pk in (72,225,779):
    entry={"product_id":pk}
    try:
        product=Product.objects.get(pk=pk)
        req=RequestFactory().get("/commerce/book/%d/"%pk,
                                  secure=True,HTTP_HOST="mojplaywin.com")
        req.user=SimpleNamespace(pk=-580001,is_authenticated=True,is_active=True,
                                 username="read-only-prepurchase")
        response=product_checkout_page(req,pk)
        rendered=response.content.decode("utf8","replace")
        entry.update(http=response.status_code,
                     auto_status="MPW_CRYPTO_AUTODELIVERY_POLL_V1" in rendered,
                     strict_script_csp="Content-Security-Policy" in rendered
                     or response.has_header("Content-Security-Policy"),
                     download_gate="can_access_purchased_items" in rendered,
                     price_positive=product.price>0,
                     currency=product.currency)
        if not(entry["http"]==200 and entry["auto_status"]
               and entry["strict_script_csp"] and entry["download_gate"]
               and entry["price_positive"] and entry["currency"]=="USD"):
            blocks.append("checkout_render_or_autodelivery_invalid:"+str(pk))
    except Exception as exc:
        blocks.append("checkout_probe_error:"+str(pk))
        entry["error"]=type(exc).__name__
    readiness.append(entry)
emit("MPW_PREBUY_CHECKOUT_RENDER",readiness)

sources={}
for name,relative in (
        ("auto_reconcile","mpw_commerce/auto_reconcile.py"),
        ("settlement","mpw_commerce/settlement.py"),
        ("entitlements","mpw_commerce/entitlements.py"),
        ("downloads","mpw_commerce/downloads.py"),
        ("checkout_views","mpw_commerce/checkout_views.py"),
        ("native_verification","mpw_commerce/chain_verification.py"),
        ("reconciler_command","mpw_commerce/management/commands/mpw_commerce_reconcile.py")):
    f=APP/relative
    if f.is_file() and not f.is_symlink():
        data=f.read_bytes()
        sources[name]={"exists":True,"sha256":hashlib.sha256(data).hexdigest()[:16],
                       "nonempty":len(data)>200}
    else:
        sources[name]={"exists":False}
        if name!="native_verification":blocks.append("missing_crypto_component:"+name)
emit("MPW_PREBUY_SOURCE_INVENTORY",sources)

try:
    res=subprocess.run(["crontab","-l"],text=True,capture_output=True,timeout=8)
    lines=res.stdout.splitlines() if res.returncode==0 else []
    jobs=[s for s in lines if "mpw_commerce_live_inbound_reconciler.py" in s
          and not s.lstrip().startswith("#")]
    cron={"crontab_readable":res.returncode==0,"jobs":len(jobs),
          "minute_cadence":len(jobs)==1 and jobs[0].strip().startswith("* * * * *"),
          "exclusive_lock":len(jobs)==1 and "flock" in jobs[0]}
    if not all((cron["crontab_readable"],cron["jobs"]==1,cron["minute_cadence"],cron["exclusive_lock"])):
        blocks.append("auto_reconcile_schedule_invalid")
except Exception as e:
    cron={"error_type":type(e).__name__}
    blocks.append("auto_reconcile_schedule_unavailable")
emit("MPW_PREBUY_CRON",cron)

log=PRIVATE/"mpw_commerce_reconcile_20261019.log"
if log.is_file() and not log.is_symlink():
    raw=log.read_bytes()[-150000:].decode("utf8","replace").splitlines()
    outcome=collections.Counter()
    last=[]
    for line in raw[-1200:]:
        if "reconcile_failed" in line: outcome["failed"]+=1
        elif "reconcile_exception" in line:outcome["exception"]+=1
        elif "reconcile_timeout" in line:outcome["timeout"]+=1
        elif "reconcile_disabled" in line:outcome["disabled"]+=1
        elif "reconcile_idle" in line:outcome["idle"]+=1
        elif "reconcile_scanned" in line:outcome["scanned"]+=1
        if any(t in line for t in ("reconcile_failed","reconcile_exception","reconcile_timeout")):
            last.append(line[:45])
    log_age=(timezone.now()-datetime.datetime.fromtimestamp(
            log.stat().st_mtime,datetime.timezone.utc)).total_seconds()
    details={"last_1200_lines":dict(outcome),"log_age_seconds":round(log_age),
             "size":log.stat().st_size}
    if log_age>180:blocks.append("payment_reconciler_not_fresh")
    if outcome["failed"] or outcome["exception"] or outcome["timeout"]:
        warnings.append("reconciliation_worker_failures_exist_in_recent_log")
else:
    details={"present":False}
    blocks.append("reconciliation_worker_log_missing")
emit("MPW_PREBUY_RECONCILER_LOG",details)

# One negative control with no ORM mutations or money: neither an anonymous nor
# a forged ID can obtain protected checkout status or download.
from django.test import Client
client=Client(enforce_csrf_checks=True)
probe={}
for path in ("/commerce/checkout/status/987654321/","/commerce/download/987654321/"):
    try:
        response=client.get(path,secure=True,HTTP_HOST="mojplaywin.com")
        probe[path]={"http":response.status_code,
                     "no_paid_pdf":not(response.status_code==200
                     and response.get("Content-Type","").startswith("application/pdf"))}
        if not probe[path]["no_paid_pdf"]:blocks.append("anonymous_file_exposure:"+path)
    except Exception as e:
        probe[path]={"exception_type":type(e).__name__}
        warnings.append("cannot_test_anonymous_route:"+path)
emit("MPW_PREBUY_ANONYMOUS_ACCESS",probe)

emit("MPW_PREBUY_GATE",{"scope":"crypto_mainnet_only",
     "blocks":sorted(set(blocks)),"warnings":sorted(set(warnings)),
     "safe_to_make_real_purchase":False,
     "reason":"Read-only source/route/cron evidence cannot establish money-safety",
     "production_writes":0,"test_purchases_created":0,"chain_transfers":0})
