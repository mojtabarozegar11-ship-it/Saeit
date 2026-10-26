#!/usr/bin/env python3
"""Readiness proof for every authorized MojPlayWin TRX product.

Runs against the live Django app through a database transaction that is ALWAYS
rolled back. Issues no real blockchain transfers and sends no email.
"""
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

APP=Path("/home/zomorod2/Saeit-staging")
os.chdir(APP)
sys.path.insert(0,str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.test import RequestFactory
from django.utils import timezone
from core.models import Product, Order, OrderItem, PaymentIntent
from services import mpw_trx_commercial_web as web
from mpw_commerce.buyer_orders import _eligible
from mpw_commerce.downloads import _private_file

assert connection.vendor == "mysql" and connection.alias == "default"
ids=tuple(getattr(settings,"MPW_TRX_PUBLIC_PRODUCT_IDS",()))
if not ids or len(ids)!=len(set(ids)) or any(type(n) is not int or n<=0 for n in ids):
    raise RuntimeError("Missing or malformed public product allowlist")
if getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False) is not True:
    raise RuntimeError("Public TRX release gate disabled")
src=PaymentIntent.objects.select_related("order").filter(provider=web.PROVIDER).order_by("-pk").first()
if src is None or not src.order.customer_id:
    raise RuntimeError("No existing verified commerce buyer context")
buyer_id=src.order.customer_id
before=(Order.objects.count(),OrderItem.objects.count(),PaymentIntent.objects.count())
# Observe precisely one trusted quote, reuse it only inside this atomic diagnostic.
rate=web._rate_provider()
if not isinstance(rate,(list,tuple)) or len(rate)!=2 or Decimal(str(rate[0]))<=0:
    raise RuntimeError("Trusted TRX price quote unavailable")
results=[]
with transaction.atomic(using="default"):
    try:
        with patch.object(web,"_rate_provider",lambda:rate):
            for pid in ids:
                p=Product.objects.get(pk=pid)
                if not _eligible(p) or p.currency!="USD" or not p.active:
                    raise RuntimeError("Sale policy gate failed for SKU "+str(pid))
                req=RequestFactory().get("/commerce/trx-easy/start/"+str(pid)+"/",
                                         secure=True,HTTP_HOST="mojplaywin.com")
                req.user=SimpleNamespace(pk=buyer_id,is_authenticated=True,is_active=True)
                response=web._start_order(req,pid)
                if response.status_code!=302:
                    raise RuntimeError("Invoice start did not redirect for "+str(pid))
                location=response["Location"]
                m=re.fullmatch(r"/commerce/trx-easy/invoice/([1-9][0-9]*)/",location)
                if not m:
                    raise RuntimeError("Unsafe invoice return path for "+str(pid))
                intent_id=int(m.group(1))
                intent=PaymentIntent.objects.select_related("order").get(pk=intent_id)
                invoice=web._decode(intent)
                if (invoice.customer_id!=buyer_id or Decimal(invoice.usd_total)!=Decimal(p.price)
                    or invoice.expires_at<=timezone.now() or invoice.amount_sun<=0):
                    raise RuntimeError("Invoice invariants failed for "+str(pid))
                view=web._show_invoice(req,intent_id)
                html=view.content.decode("utf-8")
                if (view.status_code!=200 or not view.get("Content-Security-Policy")
                    or html.count('id="mpw-open-wallet"')!=1
                    or html.count('id="mpw-open-trustwallet"')!=1
                    or html.count("MPW_TRX_MOBILE_ACTIONS_20261026")!=1
                    or "data-reconcile-url" not in html
                    or "data-csrf-token" not in html):
                    raise RuntimeError("Responsive invoice or reconciliation UI broken for "+str(pid))
                status=web._invoice_status(req,intent_id)
                if status.status_code!=200:
                    raise RuntimeError("Status endpoint failed for "+str(pid))
                state=json.loads(status.content)
                if state.get("status")!="awaiting" or state.get("can_download") is not False:
                    raise RuntimeError("Unpaid invoice could gain entitlement for "+str(pid))
                results.append({"sku":pid,"price_usd":str(p.price),"issued":True,
                                "owner_invoice":True,"unpaid_locked":True})
    finally:
        transaction.set_rollback(True,using="default")
after=(Order.objects.count(),OrderItem.objects.count(),PaymentIntent.objects.count())
if before!=after:
    raise RuntimeError("Diagnostic left an order or invoice behind")
if len(results)!=len(ids):
    raise RuntimeError("Not all sale-released products tested")
print("MPW_UNIVERSAL_TRX_ATOMIC_ROUNDTRIP="+json.dumps({"status":"PASS","items":results,"db_unchanged":True}))
