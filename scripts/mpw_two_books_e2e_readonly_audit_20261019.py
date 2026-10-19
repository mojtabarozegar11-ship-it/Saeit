#!/usr/bin/env python3
"""Read-only proof audit for the two MojPlayWin digital-book sales paths.

Reads ORM records and route/feature declarations. Does not create an order,
attempt a payment, modify customer data, disclose wallet addresses or secrets,
or download any private file.
"""
import os, sys, json, ast, hashlib
from pathlib import Path

BASE=Path("/home/zomorod2/Saeit-staging")
if not BASE.is_dir() or BASE.is_symlink():
    raise RuntimeError("Unexpected deployment root")
os.chdir(BASE);sys.path.insert(0,str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.urls import resolve
from django.apps import apps
from core.models import Product,Order,OrderItem,PaymentIntent
from core.cryptopay_checkout import product_delivery_ready
from mpw_native_checkout.wallet_ownership import proven_assets
from django.db import connection

keys = (
"MPW_COMMERCE_RELEASE_READY","MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
"MPW_COMMERCE_INVOICING_ENABLED","MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
"MPW_COMMERCE_SETTLEMENT_ENABLED","MPW_COMMERCE_REAL_RPC_ENABLED",
"MPW_COMMERCE_AUTORECONCILE_ENABLED","MPW_COMMERCE_DOWNLOADS_ENABLED",
)
results={"read_only":True, "utc_audit":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
"engine_name":settings.DATABASES['default']['ENGINE'].split(".")[-1],
"switches":{x:getattr(settings,x,False) is True for x in keys},
"authenticated_buyer_request_tested":False, "real_money_transferred":False,
"live_payment_receipt_proven_by_this_audit":False,
"private_pdf_download_to_paid_customer_tested":False}

try:
    wallet=proven_assets()
    results["wallet_proof"]={"verified_assets_count":len(wallet),"has_trx": "TRX" in str(list(wallet.keys()) if isinstance(wallet,dict) else wallet),"has_eth":"ETH" in str(list(wallet.keys()) if isinstance(wallet,dict) else wallet)}
except Exception as e:
    results["wallet_proof"]={"error_type":type(e).__name__}

ids=(72,225)
books=[]
for pk in ids:
    p=Product.objects.select_related("knowledge_article").filter(pk=pk).first()
    if not p:
        books.append({"id":pk,"exists":False})
        continue
    meta=p.metadata if isinstance(p.metadata,dict) else {}
    lines=OrderItem.objects.filter(product_id=pk)
    statuses={}
    for s in lines.values_list("order__status",flat=True):
        statuses[s]=statuses.get(s,0)+1
    entry={
        "id":pk,"exists":True,"title":p.title,"active":p.active,
        "price":str(p.price),"currency":p.currency,
        "rights_declared":meta.get("license_verified") is True,
        "quality_approved":meta.get("quality_approved") is True,
        "asset_verified":meta.get("asset_verified") is True,
        "checkout_enabled":meta.get("checkout_enabled") is True,
        "payment_live":meta.get("payment_live") is True,
        "knowledge_published":bool(p.knowledge_article_id and p.knowledge_article.published),
        "private_pdf_ready":bool(product_delivery_ready(p)),
        "book_order_statuses":statuses,
        "order_line_count":lines.count(),
        "paid_order_lines":lines.filter(order__status="paid").count(),
        "unverified_delivery_count":None,
    }
    books.append(entry)
results["books"]=books
results["order_total_for_books"]=Order.objects.filter(items__product_id__in=ids).distinct().count()
results["core_payment_intents_for_books"]=PaymentIntent.objects.filter(order__items__product_id__in=ids).distinct().count()

for mod,name in [
    ("mpw_native_checkout","NativeInvoice"),
    ("mpw_native_checkout","NativeChainTransfer"),
    ("mpw_native_checkout","MerchantWalletProof")]:
    try:
        model=apps.get_model(mod,name)
        results[name]={"count":model.objects.count(),
            "fields":[f.name for f in model._meta.fields][:45]}
    except Exception as exc:
        results[name]={"error_type":type(exc).__name__}
for path in (
    "/store/product/72/","/store/product/72/checkout/",
    "/store/product/225/","/store/product/225/checkout/",
    "/merchant-wallet/","/checkout/"):
    try:
        r=resolve(path)
        results.setdefault("routes",[]).append({"path":path,"resolved":True,
          "module":r.func.__module__,"view":getattr(r.func,"__name__",type(r.func).__name__)})
    except Exception as exc:
        results.setdefault("routes",[]).append({"path":path,"resolved":False,"error":type(exc).__name__})

for file in [
    "mpw_commerce/product_checkout_page.py",
    "mpw_commerce/buyer_orders.py",
    "mpw_commerce/invoicing.py",
    "mpw_commerce/settlement.py",
    "mpw_commerce/auto_reconcile.py",
    "mpw_commerce/downloads.py",
    "mpw_native_checkout/autopay_worker.py"]:
    p=BASE/file
    if not p.is_file() or p.is_symlink():
        results.setdefault("module_schema",[]).append({"module":file,"exists":False})
        continue
    tree=ast.parse(p.read_text("utf8","replace"))
    methods=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            name=node.name
            if any(t in name for t in ("checkout","invoice","order","reconcil","settle","download","eligible","verify","create")):
                methods.append({"function":name,"args":[a.arg for a in node.args.args][:12]})
    results.setdefault("module_schema",[]).append({"module":file,"exists":True,"functions":methods[:30]})
print("MPW_SALES_E2E_READ_ONLY_AUDIT="+json.dumps(results,sort_keys=True,default=str,ensure_ascii=False))
